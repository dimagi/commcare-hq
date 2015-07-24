from xml.etree import ElementTree
from corehq import toggles
from corehq.apps.app_manager.models import (
    get_apps_in_domain,
    Application,
    ReportModule,
    StaticChoiceListFilter,
)
from corehq.apps.userreports.reports.factory import ReportFactory
from .models import ReportConfiguration


def wrap_by_filter_type(report_app_filter):
    doc_type_to_filter_class = {
        'StaticChoiceListFilter': StaticChoiceListFilter,
    }
    filter_class = doc_type_to_filter_class.get(report_app_filter.doc_type)
    if not filter_class:
        raise Exception
    return filter_class.wrap(report_app_filter.to_json())


class ReportFixturesProvider(object):
    id = 'commcare:reports'

    def __call__(self, user, version, last_sync=None):
        """
        Generates a report fixture for mobile that can be used by a report module
        """
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
        reports_elem = ElementTree.Element('reports')
        for report_config in report_configs:
            report = ReportConfiguration.get(report_config.report_id)
            reports_elem.append(self._report_to_fixture(report, report_config.filters))
        root.append(reports_elem)
        return [root]

    def _report_to_fixture(self, report, filters):
        report_elem = ElementTree.Element('report', attrib={'id': report._id})
        report_elem.append(self._element('name', report.title))
        report_elem.append(self._element('description', report.description))
        data_source = ReportFactory.from_spec(report)
        data_source.set_filter_values({
            filter_slug: wrap_by_filter_type(filters[filter_slug]).get_filter_value()
            for filter_slug in filters
        })

        rows_elem = ElementTree.Element('rows')

        for i, row in enumerate(data_source.get_data()):
            row_elem = ElementTree.Element('row', attrib={'index': str(i)})
            for k in sorted(row.keys()):
                row_elem.append(self._element('column', self._serialize(row[k]), attrib={'id': k}))
            rows_elem.append(row_elem)

        report_elem.append(rows_elem)
        return report_elem

    @staticmethod
    def _element(name, text, attrib=None):
        attrib = attrib or {}
        element = ElementTree.Element(name, attrib=attrib)
        element.text = text
        return element

    @staticmethod
    def _serialize(value):
        # todo: be smarter than this
        return '' if value is None else unicode(value)

report_fixture_generator = ReportFixturesProvider()
