from collections import defaultdict
from datetime import datetime
import logging
import random

from couchdbkit.exceptions import NoResultFound
from django.conf import settings
from lxml.builder import E

from casexml.apps.phone.fixtures import FixtureProvider
from corehq import toggles
from corehq.apps.app_manager.const import (
    MOBILE_UCR_VERSION_1,
    MOBILE_UCR_MIGRATING_TO_2,
    MOBILE_UCR_VERSION_2,
)
from corehq.apps.app_manager.models import ReportModule
from corehq.apps.app_manager.suite_xml.features.mobile_ucr import is_valid_mobile_select_filter_type
from corehq.apps.userreports.reports.filters.factory import ReportFilterFactory
from corehq.util.xml_utils import serialize

from corehq.apps.userreports.const import UCR_ES_BACKEND, UCR_LABORATORY_BACKEND, UCR_SUPPORT_BOTH_BACKENDS
from corehq.apps.userreports.exceptions import UserReportsError, ReportConfigurationNotFoundError
from corehq.apps.userreports.models import get_report_config
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.tasks import compare_ucr_dbs
from corehq.apps.app_manager.dbaccessors import (
    get_apps_in_domain, get_brief_apps_in_domain, get_apps_by_id, get_brief_app
)

MOBILE_UCR_RANDOM_THRESHOLD = 1000


def _should_sync(restore_state):
    last_sync_log = restore_state.last_sync_log
    if not last_sync_log or restore_state.overwrite_cache:
        return True

    sync_interval = restore_state.restore_user.get_mobile_ucr_sync_interval()
    if sync_interval is None and restore_state.params.app:
        app = restore_state.params.app
        if restore_state.params.app.copy_of:
            # get sync interval from latest app version so that we don't have to deploy a new version
            # to make changes to the sync interval
            try:
                app = get_brief_app(restore_state.domain, restore_state.params.app.copy_of)
            except NoResultFound:
                pass
        sync_interval = app.mobile_ucr_sync_interval
    if sync_interval is None:
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
        report_configs = self._get_report_configs(apps).values()
        if not report_configs:
            return False

        return True

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
            for module in app_.modules if isinstance(module, ReportModule)
            for report_config in module.report_configs
        }

    @staticmethod
    def _get_report_and_data_source(report_id, domain):
        report = get_report_config(report_id, domain)[0]
        data_source = ReportFactory.from_spec(report, include_prefilters=True)
        if report.soft_rollout > 0 and data_source.config.backend_id == UCR_LABORATORY_BACKEND:
            if random.random() < report.soft_rollout:
                data_source.override_backend_id(UCR_ES_BACKEND)
        return report, data_source

    @staticmethod
    def _get_filters_elem(defer_filters, filter_options_by_field, couch_user):
        filters_elem = E.filters()
        for filter_slug, ui_filter in defer_filters.items():
            # @field is maybe a bad name for this attribute,
            # since it's actually the filter slug
            filter_elem = E.filter(field=filter_slug)
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
        if not self.uses_reports:
            return []

        restore_user = restore_state.restore_user
        apps = self._get_apps(restore_state, restore_user)
        fixtures = []

        needed_versions = {
            app.mobile_ucr_restore_version
            for app in apps
        }

        if needed_versions.intersection({MOBILE_UCR_VERSION_1, MOBILE_UCR_MIGRATING_TO_2}):
            fixtures.extend(self._v1_fixture(restore_user, self._get_report_configs(apps).values()))
        else:
            fixtures.extend(self._empty_v1_fixture(restore_user))

        return fixtures

    def _empty_v1_fixture(self, restore_user):
        return [E.fixture(id=self.id, user_id=restore_user.user_id)]

    def _v1_fixture(self, restore_user, report_configs):
        root = E.fixture(id=self.id, user_id=restore_user.user_id)
        reports_elem = E.reports(last_sync=_utcnow().isoformat())
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

        # TODO: Convert to be compatible with restore_user
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
        defer_filters = {
            filter_slug: report.get_ui_filter(filter_slug)
            for filter_slug, filter_value in all_filter_values.items()
            if filter_value is None and is_valid_mobile_select_filter_type(report.get_ui_filter(filter_slug))
        }
        data_source.set_filter_values(filter_values)
        data_source.defer_filters(defer_filters)
        filter_options_by_field = defaultdict(set)

        rows_elem = ReportFixturesProvider._get_v1_report_elem(
            data_source,
            {ui_filter.field for ui_filter in defer_filters.values()},
            filter_options_by_field
        )
        filters_elem = BaseReportFixturesProvider._get_filters_elem(
            defer_filters, filter_options_by_field, restore_user._couch_user)

        if (data_source.config.backend_id in UCR_SUPPORT_BOTH_BACKENDS and
                random.randint(0, MOBILE_UCR_RANDOM_THRESHOLD) == MOBILE_UCR_RANDOM_THRESHOLD):
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
        for i, row in enumerate(data_source.get_data()):
            rows_elem.append(_row_to_row_elem(row, i))
        if data_source.has_total_row:
            total_row = data_source.get_total_row()
            rows_elem.append(_row_to_row_elem(
                dict(
                    zip(
                        map(lambda column_config: column_config.column_id, data_source.top_level_columns),
                        map(str, total_row)
                    )
                ),
                data_source.get_total_records(),
                is_total_row=True,
            ))
        return rows_elem


class ReportFixturesProviderV2(BaseReportFixturesProvider):
    id = 'commcare-reports'

    def __call__(self, restore_state):
        """
        Generates a report fixture for mobile that can be used by a report module
        """
        if not self.uses_reports:
            return []

        restore_user = restore_state.restore_user
        apps = self._get_apps(restore_state, restore_user)
        fixtures = []

        needed_versions = {
            app.mobile_ucr_restore_version
            for app in apps
        }

        if needed_versions.intersection({MOBILE_UCR_MIGRATING_TO_2, MOBILE_UCR_VERSION_2}):
            fixtures.extend(self._v2_fixtures(restore_user, self._get_report_configs(apps).values()))

        return fixtures

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
        report_fixture_id = 'commcare-reports:' + report_config.uuid
        report_filter_id = 'commcare-reports-filters:' + report_config.uuid

        # TODO: Convert to be compatible with restore_user
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
        defer_filters = {
            filter_slug: report.get_ui_filter(filter_slug)
            for filter_slug, filter_value in all_filter_values.items()
            if filter_value is None and is_valid_mobile_select_filter_type(report.get_ui_filter(filter_slug))
        }
        data_source.set_filter_values(filter_values)
        data_source.defer_filters(defer_filters)
        filter_options_by_field = defaultdict(set)

        rows_elem = ReportFixturesProviderV2._get_v2_report_elem(
            data_source,
            {ui_filter.field for ui_filter in defer_filters.values()},
            filter_options_by_field
        )
        filters_elem = BaseReportFixturesProvider._get_filters_elem(
            defer_filters, filter_options_by_field, restore_user._couch_user)
        report_filter_elem = E.fixture(id=report_filter_id)
        report_filter_elem.append(filters_elem)

        if (data_source.config.backend_id in UCR_SUPPORT_BOTH_BACKENDS and
                random.randint(0, MOBILE_UCR_RANDOM_THRESHOLD) == MOBILE_UCR_RANDOM_THRESHOLD):
            compare_ucr_dbs.delay(domain, report_config.report_id, filter_values)

        report_elem = E.fixture(
            id=report_fixture_id, user_id=restore_user.user_id,
            report_id=report_config.report_id, last_sync=_utcnow().isoformat(),
            indexed='true'
        )
        report_elem.append(rows_elem)
        return [report_filter_elem, report_elem]

    @staticmethod
    def _get_v2_report_elem(data_source, deferred_fields, filter_options_by_field):
        def _row_to_row_elem(row, index, is_total_row=False):
            row_elem = E.row(index=str(index), is_total_row=str(is_total_row))
            for k in sorted(row.keys()):
                value = serialize(row[k])
                row_elem.append(E(k, value))
                if not is_total_row and k in deferred_fields:
                    filter_options_by_field[k].add(value)
            return row_elem

        rows_elem = E.rows()
        for i, row in enumerate(data_source.get_data()):
            rows_elem.append(_row_to_row_elem(row, i))
        if data_source.has_total_row:
            total_row = data_source.get_total_row()
            rows_elem.append(_row_to_row_elem(
                dict(
                    zip(
                        map(lambda column_config: column_config.column_id, data_source.top_level_columns),
                        map(str, total_row)
                    )
                ),
                data_source.get_total_records(),
                is_total_row=True,
            ))
        return rows_elem


def _utcnow():
    return datetime.utcnow()


report_fixture_generator = ReportFixturesProvider()
report_fixture_v2_generator = ReportFixturesProviderV2()
