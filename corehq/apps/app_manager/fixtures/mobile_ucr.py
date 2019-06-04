from __future__ import absolute_import

from __future__ import unicode_literals

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
import logging

from django.conf import settings
from lxml.builder import E

from casexml.apps.phone.fixtures import FixtureProvider
from casexml.apps.phone.models import UCRSyncLog
from corehq import toggles
from corehq.apps.app_manager.const import (
    MOBILE_UCR_VERSION_1,
    MOBILE_UCR_MIGRATING_TO_2,
    MOBILE_UCR_VERSION_2,
)
from corehq.apps.app_manager.suite_xml.features.mobile_ucr import is_valid_mobile_select_filter_type
from corehq.apps.userreports.reports.filters.factory import ReportFilterFactory
from corehq.toggles import COMPARE_UCR_REPORTS, NAMESPACE_OTHER
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.util.xml_utils import serialize

from corehq.apps.userreports.exceptions import UserReportsError, ReportConfigurationNotFoundError
from corehq.apps.userreports.models import get_report_config
from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
from corehq.apps.userreports.tasks import compare_ucr_dbs
from corehq.apps.app_manager.dbaccessors import (
    get_apps_in_domain, get_brief_apps_in_domain, get_apps_by_id
)
from six.moves import zip
from six.moves import map


def _should_sync(restore_state):
    last_sync_log = restore_state.last_sync_log
    if not last_sync_log or restore_state.overwrite_cache:
        return True

    sync_interval = restore_state.project.default_mobile_ucr_sync_interval
    sync_interval = sync_interval and sync_interval * 3600  # convert to seconds
    return (
        not last_sync_log or
        not sync_interval or
        (_utcnow() - last_sync_log.date).total_seconds() > sync_interval
    )


class BaseReportFixturesProvider(FixtureProvider):
    def uses_reports(self, restore_state):
        restore_user = restore_state.restore_user
        if not toggles.MOBILE_UCR.enabled(restore_user.domain) or not _should_sync(restore_state):
            return False

        if toggles.PREVENT_MOBILE_UCR_SYNC.enabled(restore_user.domain):
            return False

        apps = self._get_apps(restore_state, restore_user)
        return bool(self._get_report_configs(apps))

    def _get_apps(self, restore_state, restore_user):
        app_aware_sync_app = restore_state.params.app

        if app_aware_sync_app:
            apps = [app_aware_sync_app]
        elif (
                toggles.ROLE_WEBAPPS_PERMISSIONS.enabled(restore_user.domain)
                and restore_state.params.device_id
                and "WebAppsLogin" in restore_state.params.device_id
        ):
            # Only sync reports for apps the user has access to if this is a restore from webapps
            role = restore_user.get_role(restore_user.domain)
            if role:
                allowed_app_ids = [app['_id'] for app in get_brief_apps_in_domain(restore_user.domain)
                                   if role.permissions.view_web_app(app)]
                apps = get_apps_by_id(restore_user.domain, allowed_app_ids)
            else:
                # If there is no role, allow access to all apps
                apps = get_apps_in_domain(restore_user.domain, include_remote=False)
        else:
            apps = get_apps_in_domain(restore_user.domain, include_remote=False)

        return apps

    def _get_report_configs(self, apps):
        return {
            report_config.uuid: report_config
            for app_ in apps
            for module in app_.get_report_modules()
            for report_config in module.report_configs
        }

    @staticmethod
    def _get_report_and_data_source(report_id, domain):
        report = get_report_config(report_id, domain)[0]
        data_source = ConfigurableReportDataSource.from_spec(report, include_prefilters=True)
        return report, data_source

    @staticmethod
    def _get_filters_elem(defer_filters, filter_options_by_field, couch_user):
        filters_elem = E.filters()
        for ui_filter in defer_filters:
            # @field is maybe a bad name for this attribute,
            # since it's actually the filter name
            filter_elem = E.filter(field=ui_filter.name)
            option_values = filter_options_by_field[ui_filter.field]
            choices = ui_filter.choice_provider.get_sorted_choices_for_values(option_values, couch_user)
            for choice in choices:
                # add the correct text from ui_filter.choice_provider
                option_elem = E.option(choice.display, value=choice.value)
                filter_elem.append(option_elem)
            filters_elem.append(filter_elem)
        return filters_elem


class ReportFixturesProvider(BaseReportFixturesProvider):
    id = 'commcare:reports'

    def __call__(self, restore_state):
        """
        Generates a report fixture for mobile that can be used by a report module
        """
        if not self.uses_reports(restore_state):
            return []

        restore_user = restore_state.restore_user
        apps = self._get_apps(restore_state, restore_user)
        fixtures = []

        needed_versions = {
            app.mobile_ucr_restore_version
            for app in apps
        }

        if needed_versions.intersection({MOBILE_UCR_VERSION_1, MOBILE_UCR_MIGRATING_TO_2}):
            fixtures.extend(self._v1_fixture(restore_user, list(self._get_report_configs(apps).values())))
        else:
            fixtures.extend(self._empty_v1_fixture(restore_user))

        return fixtures

    def _empty_v1_fixture(self, restore_user):
        return [E.fixture(id=self.id, user_id=restore_user.user_id)]

    def _v1_fixture(self, restore_user, report_configs):
        user_id = restore_user.user_id
        root = E.fixture(id=self.id, user_id=user_id)
        reports_elem = E.reports(last_sync=_last_sync_time(restore_user.domain, user_id))
        for report_config in report_configs:
            try:
                reports_elem.append(self.report_config_to_v1_fixture(report_config, restore_user))
            except ReportConfigurationNotFoundError as err:
                logging.exception('Error generating report fixture: {}'.format(err))
                continue
            except UserReportsError:
                if settings.UNIT_TESTING or settings.DEBUG:
                    raise
            except Exception as err:
                logging.exception('Error generating report fixture: {}'.format(err))
                if settings.UNIT_TESTING or settings.DEBUG:
                    raise
        root.append(reports_elem)
        return [root]

    @staticmethod
    def report_config_to_v1_fixture(report_config, restore_user):
        domain = restore_user.domain
        report, data_source = BaseReportFixturesProvider._get_report_and_data_source(
            report_config.report_id, domain
        )

        # apply filters specified in report module
        all_filter_values = {
            filter_slug: restore_user.get_ucr_filter_value(filter, report.get_ui_filter(filter_slug))
            for filter_slug, filter in report_config.filters.items()
        }
        # apply all prefilters
        prefilters = [ReportFilterFactory.from_spec(p, report) for p in report.prefilters]
        prefilter_values = {prefilter.name: prefilter.value() for prefilter in prefilters}
        all_filter_values.update(prefilter_values)
        # filter out nulls
        filter_values = {
            filter_slug: filter_value for filter_slug, filter_value in all_filter_values.items()
            if filter_value is not None
        }
        defer_filters = [
            report.get_ui_filter(filter_slug)
            for filter_slug, filter_value in all_filter_values.items()
            if filter_value is None and is_valid_mobile_select_filter_type(report.get_ui_filter(filter_slug))
        ]
        data_source.set_filter_values(filter_values)
        data_source.set_defer_fields([f.field for f in defer_filters])
        filter_options_by_field = defaultdict(set)

        rows_elem = ReportFixturesProvider._get_v1_report_elem(
            data_source,
            {ui_filter.field for ui_filter in defer_filters},
            filter_options_by_field
        )
        filters_elem = BaseReportFixturesProvider._get_filters_elem(
            defer_filters, filter_options_by_field, restore_user._couch_user)

        if (report_config.report_id in settings.UCR_COMPARISONS and
                COMPARE_UCR_REPORTS.enabled(uuid.uuid4().hex, NAMESPACE_OTHER)):
            compare_ucr_dbs.delay(domain, report_config.report_id, filter_values)

        report_elem = E.report(id=report_config.uuid, report_id=report_config.report_id)
        report_elem.append(filters_elem)
        report_elem.append(rows_elem)
        return report_elem

    @staticmethod
    def _get_v1_report_elem(data_source, deferred_fields, filter_options_by_field):
        def _row_to_row_elem(row, index, is_total_row=False):
            row_elem = E.row(index=str(index), is_total_row=str(is_total_row))
            for k in sorted(row.keys()):
                value = serialize(row[k])
                row_elem.append(E.column(value, id=k))
                if not is_total_row and k in deferred_fields:
                    filter_options_by_field[k].add(value)
            return row_elem

        rows_elem = E.rows()
        row_index = 0
        for row_index, row in enumerate(data_source.get_data()):
            rows_elem.append(_row_to_row_elem(row, row_index))
        if data_source.has_total_row:
            total_row = data_source.get_total_row()
            rows_elem.append(_row_to_row_elem(
                dict(
                    zip(
                        [column_config.column_id for column_config in data_source.top_level_columns],
                        list(map(str, total_row))
                    )
                ),
                row_index + 1,
                is_total_row=True,
            ))
        return rows_elem


class ReportFixturesProviderV2(BaseReportFixturesProvider):
    id = 'commcare-reports'

    def __call__(self, restore_state):
        """
        Generates a report fixture for mobile that can be used by a report module
        """
        if not self.uses_reports(restore_state):
            return []

        restore_user = restore_state.restore_user
        apps = self._get_apps(restore_state, restore_user)
        fixtures = []

        needed_versions = {
            app.mobile_ucr_restore_version
            for app in apps
        }

        if needed_versions.intersection({MOBILE_UCR_MIGRATING_TO_2, MOBILE_UCR_VERSION_2}):
            report_configs = list(self._get_report_configs(apps).values())
            synced_fixtures, purged_fixture_ids = self._relevant_report_configs(restore_state, report_configs)
            fixtures.extend(self._v2_fixtures(restore_user, synced_fixtures))
            for report_uuid in purged_fixture_ids:
                fixtures.extend(self._empty_v2_fixtures(report_uuid))

        return fixtures

    def _relevant_report_configs(self, restore_state, report_configs):
        """
        Filter out any UCRs that are already synced. This can't exist in V1,
        because in V1 we send all reports as one fixture.

        Returns a list of full ReportConfigs to sync and a set of report ids to purge
        """
        last_sync_log = restore_state.last_sync_log

        if not last_sync_log or restore_state.overwrite_cache:
            return report_configs, []

        current_sync_log = restore_state.current_sync_log
        now = _utcnow()

        last_ucr_syncs = {
            log.report_uuid: log.datetime
            for log in last_sync_log.last_ucr_sync_times
        }
        configs_to_sync = []

        for config in report_configs:
            if config.uuid not in last_ucr_syncs:
                configs_to_sync.append(config)
                current_sync_log.last_ucr_sync_times.append(
                    UCRSyncLog(report_uuid=config.uuid, datetime=now)
                )
                continue

            last_sync = last_ucr_syncs[config.uuid]
            next_sync = last_sync + timedelta(hours=float(config.sync_delay))

            if now > next_sync:
                configs_to_sync.append(config)
                current_sync_log.last_ucr_sync_times.append(
                    UCRSyncLog(report_uuid=config.uuid, datetime=now)
                )
            else:
                current_sync_log.last_ucr_sync_times.append(
                    UCRSyncLog(report_uuid=config.uuid, datetime=last_sync)
                )

        config_uuids = {config.uuid for config in report_configs}
        extra_configs_on_phone = set(last_ucr_syncs.keys()).difference(config_uuids)

        return configs_to_sync, extra_configs_on_phone

    def _empty_v2_fixtures(self, report_uuid):
        return [
            E.fixture(id=self._report_fixture_id(report_uuid)),
            E.fixture(id=self._report_filter_id(report_uuid))
        ]

    def _v2_fixtures(self, restore_user, report_configs):
        fixtures = []
        for report_config in report_configs:
            try:
                fixtures.extend(self.report_config_to_v2_fixture(report_config, restore_user))
            except ReportConfigurationNotFoundError as err:
                logging.exception('Error generating report fixture: {}'.format(err))
                continue
            except UserReportsError:
                if settings.UNIT_TESTING or settings.DEBUG:
                    raise
            except Exception as err:
                logging.exception('Error generating report fixture: {}'.format(err))
                if settings.UNIT_TESTING or settings.DEBUG:
                    raise
        return fixtures

    @staticmethod
    def report_config_to_v2_fixture(report_config, restore_user):
        domain = restore_user.domain
        report, data_source = BaseReportFixturesProvider._get_report_and_data_source(
            report_config.report_id, domain)

        # apply filters specified in report module
        all_filter_values = {
            filter_slug: restore_user.get_ucr_filter_value(filter, report.get_ui_filter(filter_slug))
            for filter_slug, filter in report_config.filters.items()
        }
        # apply all prefilters
        prefilters = [ReportFilterFactory.from_spec(p, report) for p in report.prefilters]
        prefilter_values = {prefilter.name: prefilter.value() for prefilter in prefilters}
        all_filter_values.update(prefilter_values)
        # filter out nulls
        filter_values = {
            filter_slug: filter_value for filter_slug, filter_value in all_filter_values.items()
            if filter_value is not None
        }
        defer_filters = [
            report.get_ui_filter(filter_slug)
            for filter_slug, filter_value in all_filter_values.items()
            if filter_value is None and is_valid_mobile_select_filter_type(report.get_ui_filter(filter_slug))
        ]
        data_source.set_filter_values(filter_values)
        data_source.set_defer_fields([f.field for f in defer_filters])
        filter_options_by_field = defaultdict(set)

        rows_elem = ReportFixturesProviderV2._get_v2_report_elem(
            data_source,
            {f.field for f in defer_filters},
            filter_options_by_field,
            _last_sync_time(domain, restore_user.user_id),
        )
        filters_elem = BaseReportFixturesProvider._get_filters_elem(
            defer_filters, filter_options_by_field, restore_user._couch_user)
        report_filter_elem = E.fixture(id=ReportFixturesProviderV2._report_filter_id(report_config.uuid))
        report_filter_elem.append(filters_elem)

        if (report_config.report_id in settings.UCR_COMPARISONS and
                COMPARE_UCR_REPORTS.enabled(uuid.uuid4().hex, NAMESPACE_OTHER)):
            compare_ucr_dbs.delay(domain, report_config.report_id, filter_values)

        report_elem = E.fixture(
            id=ReportFixturesProviderV2._report_fixture_id(report_config.uuid), user_id=restore_user.user_id,
            report_id=report_config.report_id, indexed='true'
        )
        report_elem.append(rows_elem)
        return [report_filter_elem, report_elem]

    @staticmethod
    def _get_v2_report_elem(data_source, deferred_fields, filter_options_by_field, last_sync):
        def _row_to_row_elem(row, index, is_total_row=False):
            row_elem = E.row(index=str(index), is_total_row=str(is_total_row))
            for k in sorted(row.keys()):
                value = serialize(row[k])
                row_elem.append(E(k, value))
                if not is_total_row and k in deferred_fields:
                    filter_options_by_field[k].add(value)
            return row_elem

        rows_elem = E.rows(last_sync=last_sync)
        row_index = 0
        for row_index, row in enumerate(data_source.get_data()):
            rows_elem.append(_row_to_row_elem(row, row_index))
        if data_source.has_total_row:
            total_row = data_source.get_total_row()
            rows_elem.append(_row_to_row_elem(
                dict(
                    zip(
                        [column_config.column_id for column_config in data_source.top_level_columns],
                        list(map(str, total_row))
                    )
                ),
                row_index + 1,
                is_total_row=True,
            ))
        return rows_elem

    @staticmethod
    def _report_fixture_id(report_uuid):
        return 'commcare-reports:' + report_uuid

    @staticmethod
    def _report_filter_id(report_uuid):
        return 'commcare-reports-filters:' + report_uuid


def _utcnow():
    return datetime.utcnow()


def _last_sync_time(domain, user_id):
    timezone = get_timezone_for_user(user_id, domain)
    return ServerTime(_utcnow()).user_time(timezone).done().isoformat()


report_fixture_generator = ReportFixturesProvider()
report_fixture_v2_generator = ReportFixturesProviderV2()
