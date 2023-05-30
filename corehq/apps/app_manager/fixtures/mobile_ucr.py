import logging
import numbers
import uuid
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta

from django.conf import settings
from django.utils.translation import gettext

from lxml.builder import E

from casexml.apps.phone.fixtures import FixtureProvider
from casexml.apps.phone.models import UCRSyncLog

from corehq import toggles
from corehq.apps.app_manager.const import (
    MOBILE_UCR_MIGRATING_TO_2,
    MOBILE_UCR_VERSION_1,
    MOBILE_UCR_VERSION_2,
)
from corehq.apps.app_manager.dbaccessors import (
    get_apps_in_domain,
)
from corehq.apps.app_manager.suite_xml.features.mobile_ucr import (
    is_valid_mobile_select_filter_type,
)
from corehq.apps.userreports.exceptions import (
    ReportConfigurationNotFoundError,
    UserReportsError,
)
from corehq.apps.userreports.models import get_report_config
from corehq.apps.userreports.reports.data_source import (
    ConfigurableReportDataSource,
)
from corehq.apps.userreports.reports.filters.factory import ReportFilterFactory
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.util.xml_utils import serialize


def _should_sync(restore_state):
    # Sync if this is a forced refresh
    if restore_state.overwrite_cache:
        return True

    # Sync if this is a non-incremental restore
    last_sync_log = restore_state.last_sync_log
    if not last_sync_log:
        return True

    # Sync if the build changed, since that might have changed report-related content
    if restore_state.params.app and last_sync_log.build_id:
        if restore_state.params.app.get_id != last_sync_log.build_id:
            return True

    # If the project is limiting UCR sync frequency, only sync if the specified interval has passed
    if restore_state.project.default_mobile_ucr_sync_interval:
        sync_interval = restore_state.project.default_mobile_ucr_sync_interval * 3600  # convert to seconds
        return (_utcnow() - last_sync_log.date).total_seconds() > sync_interval

    # Default to syncing
    return True


class ReportFixturesProvider(FixtureProvider):
    id = 'commcare-reports-v1-v2'

    def __call__(self, restore_state):
        """
        Generates a report fixture for mobile that can be used by a report module
        """
        if not self.should_sync(restore_state):
            return []

        restore_user = restore_state.restore_user
        apps = self._get_apps(restore_state, restore_user)
        report_configs = self._get_report_configs(apps)
        if not report_configs:
            return []

        fixtures = []

        needed_versions = {
            app.mobile_ucr_restore_version
            for app in apps
        }

        report_data_cache = ReportDataCache()
        providers = [
            ReportFixturesProviderV1(report_data_cache),
            ReportFixturesProviderV2(report_data_cache)
        ]

        for provider in providers:
            fixtures.extend(provider(restore_state, restore_user, needed_versions, report_configs))

        return fixtures

    def should_sync(self, restore_state):
        restore_user = restore_state.restore_user
        if not toggles.MOBILE_UCR.enabled(restore_user.domain) or not _should_sync(restore_state):
            return False

        if toggles.PREVENT_MOBILE_UCR_SYNC.enabled(restore_user.domain):
            return False

        return True

    def _get_apps(self, restore_state, restore_user):
        app_aware_sync_app = restore_state.params.app

        if app_aware_sync_app:
            apps = [app_aware_sync_app]
        else:
            apps = get_apps_in_domain(restore_user.domain, include_remote=False)

        return apps

    def _get_report_configs(self, apps):
        return [
            report_config
            for app_ in apps
            for module in app_.get_report_modules()
            for report_config in module.report_configs
        ]


report_fixture_generator = ReportFixturesProvider()


class ReportDataCache(object):
    def __init__(self):
        self.data_cache = {}
        self.total_row_cache = {}

    def get_data(self, key, data_source):
        if key not in self.data_cache:
            self.data_cache[key] = data_source.get_data()
        return self.data_cache[key]


def _get_report_index_fixture(restore_user, oldest_sync_time=None):
    last_sync_time = _format_last_sync_time(restore_user, oldest_sync_time)
    return E.fixture(
        E.report_index(E.reports(last_update=last_sync_time)),
        id='commcare-reports:index', user_id=restore_user.user_id,
    )


class BaseReportFixtureProvider(metaclass=ABCMeta):
    def __init__(self, report_data_cache=None):
        self.report_data_cache = report_data_cache or ReportDataCache()

    @abstractmethod
    def __call__(self, restore_state, restore_user, needed_versions, report_configs):
        raise NotImplementedError

    @abstractmethod
    def report_config_to_fixture(self, report_config, restore_user):
        """Standard function for testing
        :returns: list of fixture elements"""
        raise NotImplementedError


class ReportFixturesProviderV1(BaseReportFixtureProvider):
    id = 'commcare:reports'

    def __call__(self, restore_state, restore_user, needed_versions, report_configs):
        """
        Generates a report fixture for mobile that can be used by a report module
        """
        fixtures = []
        if needed_versions.intersection({MOBILE_UCR_VERSION_1, MOBILE_UCR_MIGRATING_TO_2}):
            fixtures.append(_get_report_index_fixture(restore_user))
            fixtures.extend(self._v1_fixture(restore_user, report_configs, restore_state.params.fail_hard))
        else:
            fixtures.extend(self._empty_v1_fixture(restore_user))

        return fixtures

    def _empty_v1_fixture(self, restore_user):
        return [E.fixture(id=self.id, user_id=restore_user.user_id)]

    def _v1_fixture(self, restore_user, report_configs, fail_hard=False):
        user_id = restore_user.user_id
        root = E.fixture(id=self.id, user_id=user_id)
        reports_elem = E.reports(last_sync=_format_last_sync_time(restore_user))
        for report_config in report_configs:
            try:
                reports_elem.extend(self.report_config_to_fixture(report_config, restore_user))
            except ReportConfigurationNotFoundError as err:
                logging.exception('Error generating report fixture: {}'.format(err))
                if fail_hard:
                    raise
                continue
            except UserReportsError:
                if settings.UNIT_TESTING or settings.DEBUG or fail_hard:
                    raise
            except Exception as err:
                logging.exception('Error generating report fixture: {}'.format(err))
                if settings.UNIT_TESTING or settings.DEBUG or fail_hard:
                    raise
        root.append(reports_elem)
        return [root]

    def report_config_to_fixture(self, report_config, restore_user):
        def _row_to_row_elem(deferred_fields, filter_options_by_field, row, index, is_total_row=False):
            row_elem = E.row(index=str(index), is_total_row=str(is_total_row))
            if toggles.ADD_ROW_INDEX_TO_MOBILE_UCRS.enabled(restore_user.domain):
                row_elem.append(E.column(str(index), id='row_index'))
            for k in sorted(row.keys()):
                value = serialize(row[k])
                row_elem.append(E.column(value, id=k))
                if not is_total_row and k in deferred_fields:
                    filter_options_by_field[k].add(value)
            return row_elem

        row_elements, filters_elem = generate_rows_and_filters(
            self.report_data_cache, report_config, restore_user, _row_to_row_elem
        )
        rows_elem = E.rows()
        for row in row_elements:
            rows_elem.append(row)

        report_elem = E.report(id=report_config.uuid, report_id=report_config.report_id)
        report_elem.append(filters_elem)
        report_elem.append(rows_elem)
        return [report_elem]


class ReportFixturesProviderV2(BaseReportFixtureProvider):
    id = 'commcare-reports'

    def __call__(self, restore_state, restore_user, needed_versions, report_configs):
        """
        Generates a report fixture for mobile that can be used by a report module
        """
        fixtures = []

        if needed_versions.intersection({MOBILE_UCR_MIGRATING_TO_2, MOBILE_UCR_VERSION_2}):
            synced_fixtures, purged_fixture_ids = self._relevant_report_configs(restore_state, report_configs)

            oldest_sync_time = self._get_oldest_sync_time(restore_state, synced_fixtures, purged_fixture_ids)
            fixtures.append(_get_report_index_fixture(restore_user, oldest_sync_time))
            fixtures.extend(self._v2_fixtures(restore_user, synced_fixtures, restore_state.params.fail_hard))
            for report_uuid in purged_fixture_ids:
                fixtures.extend(self._empty_v2_fixtures(report_uuid))

        return fixtures

    @staticmethod
    def _get_oldest_sync_time(restore_state, synced_fixtures, purged_fixture_ids):
        """
        Get the oldest sync time for all reports.
        """
        last_sync_log = restore_state.last_sync_log
        now = _utcnow()
        if not last_sync_log or restore_state.overwrite_cache:
            return now

        # ignore reports that are being purged or are being synced now
        reports_to_ignore = purged_fixture_ids | {config.uuid for config in synced_fixtures}
        last_sync_times = [
            log.datetime
            for log in last_sync_log.last_ucr_sync_times
            if log.report_uuid not in reports_to_ignore
        ]
        return sorted(last_sync_times)[0] if last_sync_times else now

    @staticmethod
    def _relevant_report_configs(restore_state, report_configs):
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

    def _v2_fixtures(self, restore_user, report_configs, fail_hard=False):
        fixtures = []
        for report_config in report_configs:
            try:
                fixtures.extend(self.report_config_to_fixture(report_config, restore_user))
            except ReportConfigurationNotFoundError as err:
                logging.exception('Error generating report fixture: {}'.format(err))
                if fail_hard:
                    raise
                continue
            except UserReportsError:
                if settings.UNIT_TESTING or settings.DEBUG or fail_hard:
                    raise
            except Exception as err:
                logging.exception('Error generating report fixture: {}'.format(err))
                if settings.UNIT_TESTING or settings.DEBUG or fail_hard:
                    raise
        return fixtures

    def report_config_to_fixture(self, report_config, restore_user):
        def _row_to_row_elem(deferred_fields, filter_options_by_field, row, index, is_total_row=False):
            row_elem = E.row(index=str(index), is_total_row=str(is_total_row))
            if toggles.ADD_ROW_INDEX_TO_MOBILE_UCRS.enabled(restore_user.domain):
                row_elem.append(E('row_index', str(index)))
            for k in sorted(row.keys()):
                value = serialize(row[k])
                row_elem.append(E(k, value))
                if not is_total_row and k in deferred_fields:
                    filter_options_by_field[k].add(value)
            return row_elem

        rows, filters_elem = generate_rows_and_filters(
            self.report_data_cache, report_config, restore_user, _row_to_row_elem
        )
        rows_elem = E.rows(last_sync=_format_last_sync_time(restore_user))
        for row in rows:
            rows_elem.append(row)

        report_filter_elem = E.fixture(id=ReportFixturesProviderV2._report_filter_id(report_config.uuid))
        report_filter_elem.append(filters_elem)

        report_elem = E.fixture(
            id=ReportFixturesProviderV2._report_fixture_id(report_config.uuid), user_id=restore_user.user_id,
            report_id=report_config.report_id, indexed='true'
        )
        report_elem.append(rows_elem)
        return [report_filter_elem, report_elem]

    @staticmethod
    def _report_fixture_id(report_uuid):
        return 'commcare-reports:' + report_uuid

    @staticmethod
    def _report_filter_id(report_uuid):
        return 'commcare-reports-filters:' + report_uuid


def _utcnow():
    return datetime.utcnow()


def _format_last_sync_time(restore_user, sync_time=None):
    sync_time = sync_time or _utcnow()
    timezone = get_timezone_for_user(restore_user._couch_user, restore_user.domain)
    return ServerTime(sync_time).user_time(timezone).done().isoformat()


def generate_rows_and_filters(report_data_cache, report_config, restore_user, row_to_element):
    """Generate restore row and filter elements
    :param row_to_element: function (
                deferred_fields, filter_options_by_field, row, index, is_total_row
            ) -> row_element
    """
    domain = restore_user.domain
    report, data_source = _get_report_and_data_source(report_config.report_id, domain)

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

    row_elements = get_report_element(
        report_data_cache,
        report_config,
        data_source,
        {f.field for f in defer_filters},
        filter_options_by_field,
        row_to_element,
    )
    filters_elem = _get_filters_elem(defer_filters, filter_options_by_field, restore_user._couch_user)

    return row_elements, filters_elem


def get_report_element(report_data_cache, report_config, data_source, deferred_fields, filter_options_by_field, row_to_element):
    """
    :param row_to_element: function (
                deferred_fields, filter_options_by_field, row, index, is_total_row
            ) -> row_element
    """
    if data_source.has_total_row:
        total_row_calculator = IterativeTotalRowCalculator(data_source)
    else:
        total_row_calculator = MockTotalRowCalculator()

    row_elements = []
    row_index = 0
    rows = report_data_cache.get_data(report_config.uuid, data_source)
    for row_index, row in enumerate(rows):
        row_elements.append(row_to_element(deferred_fields, filter_options_by_field, row, row_index))
        total_row_calculator.update_totals(row)

    if data_source.has_total_row:
        total_row = total_row_calculator.get_total_row()
        row_elements.append(row_to_element(
            deferred_fields, filter_options_by_field,
            dict(
                zip(
                    list(data_source.final_column_ids),
                    list(map(str, total_row))
                )
            ),
            row_index + 1,
            is_total_row=True,
        ))
    return row_elements


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


def _get_report_and_data_source(report_id, domain):
    report = get_report_config(report_id, domain)[0]
    data_source = ConfigurableReportDataSource.from_spec(report, include_prefilters=True)
    return report, data_source


class MockTotalRowCalculator(object):
    def update_totals(self, row):
        pass

    def get_total_row(self):
        pass


class IterativeTotalRowCalculator(MockTotalRowCalculator):
    def __init__(self, data_source):
        self.data_source = data_source
        self.total_column_ids = data_source.total_column_ids
        self.total_cols = {col_id: 0 for col_id in self.total_column_ids}

    def update_totals(self, row):
        for col_id in self.total_column_ids:
            val = row[col_id]
            if isinstance(val, numbers.Number):
                self.total_cols[col_id] += val

    def get_total_row(self):
        total_row = [
            self.total_cols.get(col_id, '')
            for col_id in self.data_source.final_column_ids
        ]
        if total_row and total_row[0] == '':
            total_row[0] = gettext('Total')
        return total_row
