from collections import defaultdict
from datetime import datetime
import logging
from xml.etree import ElementTree
from django.conf import settings

from corehq import toggles
from corehq.apps.app_manager.models import (
    Application,
    ReportModule,
)
from corehq.util.xml_utils import serialize

from corehq.apps.userreports.exceptions import UserReportsError
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.reports.util import (
    get_expanded_columns,
    get_total_row,
)


class ReportFixturesProvider(object):
    id = 'commcare:reports'

    def __call__(self, user, version, last_sync=None):
        """
        Generates a report fixture for mobile that can be used by a report module
        """
        # delay import so that get_apps_in_domain is mockable
        from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
        if not toggles.MOBILE_UCR.enabled(user.domain):
            return []

        report_configs = [
            report_config
            for app in get_apps_in_domain(user.domain) if isinstance(app, Application)
            # TODO: pass app_id to reduce size of fixture
            for module in app.modules if isinstance(module, ReportModule)
            for report_config in module.report_configs
        ]
        if not report_configs:
            return []

        root = ElementTree.Element('fixture', attrib={'id': self.id})
        reports_elem = ElementTree.Element(
            'reports',
            attrib={
                'last_sync': datetime.utcnow().isoformat(),
            },
        )
        for report_config in report_configs:
            try:
                reports_elem.append(self._report_config_to_fixture(report_config, user))
            except UserReportsError:
                if settings.UNIT_TESTING or settings.DEBUG:
                    raise
            except Exception as err:
                logging.exception('Error generating report fixture: {}'.format(err))
                if settings.UNIT_TESTING or settings.DEBUG:
                    raise
        root.append(reports_elem)
        return [root]

    def _report_config_to_fixture(self, report_config, user):
        report_elem = ElementTree.Element('report', attrib={'id': report_config.uuid})
        report = ReportConfiguration.get(report_config.report_id)
        data_source = ReportFactory.from_spec(report)

        all_filter_values = {
            filter_slug: filter.get_filter_value(user)
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

        rows_elem = ElementTree.Element('rows')

        deferred_fields = {ui_filter.field for ui_filter in defer_filters.values()}
        filter_options_by_field = defaultdict(set)

        def _row_to_row_elem(row, index, is_total_row=False):
            row_elem = ElementTree.Element(
                'row',
                attrib={
                    'index': str(i),
                    'is_total_row': str(is_total_row),
                }
            )
            for k in sorted(row.keys()):
                value = serialize(row[k])
                row_elem.append(self._element('column', value, attrib={'id': k}))
                if k in deferred_fields:
                    filter_options_by_field[k].add(value)
            return row_elem

        for i, row in enumerate(data_source.get_data()):
            rows_elem.append(_row_to_row_elem(row, i))

        if data_source.has_total_row:
            total_row = get_total_row(
                data_source.get_data(),
                data_source.aggregation_columns,
                data_source.column_configs,
                get_expanded_columns(data_source.column_configs, data_source.config)
            )
            rows_elem.append(_row_to_row_elem(
                total_row, data_source.get_total_records(),
                is_total_row=True,
            ))

        filters_elem = self._element('filters')
        for filter_slug, ui_filter in defer_filters.items():
            # @field is maybe a bad name for this attribute,
            # since it's actually the filter slug
            filter_elem = self._element('filter', attrib={'field': filter_slug})
            option_values = filter_options_by_field[ui_filter.field]
            choices = ui_filter.choice_provider.get_choices_for_values(option_values)
            choices = sorted(choices, key=lambda choice: choice.display)
            for choice in choices:
                # add the correct text from ui_filter.choice_provider
                option_elem = self._element(
                    'option', text=choice.display, attrib={'value': choice.value})
                filter_elem.append(option_elem)
            filters_elem.append(filter_elem)

        report_elem.append(filters_elem)
        report_elem.append(rows_elem)
        return report_elem

    @staticmethod
    def _element(name, text=None, attrib=None):
        attrib = attrib or {}
        element = ElementTree.Element(name, attrib=attrib)
        element.text = text
        return element

report_fixture_generator = ReportFixturesProvider()
