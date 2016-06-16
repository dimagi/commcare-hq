from collections import defaultdict
from datetime import datetime
import logging
from lxml.builder import E
from django.conf import settings

from casexml.apps.phone.models import OTARestoreUser

from corehq import toggles
from corehq.apps.app_manager.models import ReportModule
from corehq.util.xml_utils import serialize

from corehq.apps.userreports.exceptions import UserReportsError, ReportConfigurationNotFoundError
from corehq.apps.userreports.models import get_report_config
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain


class ReportFixturesProvider(object):
    id = 'commcare:reports'

    def __call__(self, restore_user, version, last_sync=None, app=None):
        """
        Generates a report fixture for mobile that can be used by a report module
        """
        assert isinstance(restore_user, OTARestoreUser)

        if not toggles.MOBILE_UCR.enabled(restore_user.domain):
            return []

        apps = [app] if app else (a for a in get_apps_in_domain(restore_user.domain, include_remote=False))
        report_configs = [
            report_config
            for app_ in apps
            for module in app_.modules if isinstance(module, ReportModule)
            for report_config in module.report_configs
        ]
        if not report_configs:
            return []

        root = E.fixture(id=self.id)
        reports_elem = E.reports(last_sync=datetime.utcnow().isoformat())
        for report_config in report_configs:
            try:
                reports_elem.append(self._report_config_to_fixture(report_config, restore_user))
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
    def _report_config_to_fixture(report_config, restore_user):
        report, data_source = ReportFixturesProvider._get_report_and_data_source(
            report_config.report_id, restore_user.domain
        )

        # TODO: Convert to be compatiable with restore_user
        all_filter_values = {
            filter_slug: restore_user.get_ucr_filter_value(filter, report.get_ui_filter(filter_slug))
            for filter_slug, filter in report_config.filters.items()
        }
        filter_values = {
            filter_slug: filter_value for filter_slug, filter_value in all_filter_values.items()
            if filter_value is not None
        }
        defer_filters = {
            filter_slug: report.get_ui_filter(filter_slug)
            for filter_slug, filter_value in all_filter_values.items()
            if filter_value is None
        }
        data_source.set_filter_values(filter_values)
        data_source.defer_filters(defer_filters)
        filter_options_by_field = defaultdict(set)

        rows_elem = ReportFixturesProvider._get_report_elem(
            data_source,
            {ui_filter.field for ui_filter in defer_filters.values()},
            filter_options_by_field
        )
        filters_elem = ReportFixturesProvider._get_filters_elem(defer_filters, filter_options_by_field)

        report_elem = E.report(id=report_config.uuid)
        report_elem.append(filters_elem)
        report_elem.append(rows_elem)
        return report_elem

    @staticmethod
    def _get_report_and_data_source(report_id, domain):
        report = get_report_config(report_id, domain)[0]
        data_source = ReportFactory.from_spec(report)
        return report, data_source

    @staticmethod
    def _get_filters_elem(defer_filters, filter_options_by_field):
        filters_elem = E.filters()
        for filter_slug, ui_filter in defer_filters.items():
            # @field is maybe a bad name for this attribute,
            # since it's actually the filter slug
            filter_elem = E.filter(field=filter_slug)
            option_values = filter_options_by_field[ui_filter.field]
            choices = ui_filter.choice_provider.get_sorted_choices_for_values(option_values)
            for choice in choices:
                # add the correct text from ui_filter.choice_provider
                option_elem = E.option(choice.display, value=choice.value)
                filter_elem.append(option_elem)
            filters_elem.append(filter_elem)
        return filters_elem

    @staticmethod
    def _get_report_elem(data_source, deferred_fields, filter_options_by_field):
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
                        map(lambda column_config: column_config.column_id, data_source.column_configs),
                        map(str, total_row)
                    )
                ),
                data_source.get_total_records(),
                is_total_row=True,
            ))
        return rows_elem


report_fixture_generator = ReportFixturesProvider()
