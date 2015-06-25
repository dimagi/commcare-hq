import json
from xml.etree import ElementTree
from corehq import toggles
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.reports.specs import MultibarChartSpec
from .models import ReportConfiguration


class ReportFixturesProvider(object):
    id = 'commcare:reports'

    def __call__(self, user, version, last_sync=None):
        """
        Generates a report fixture for mobile that can be used by a report module
        """
        if not toggles.MOBILE_UCR.enabled(user.domain):
            return []

        reports = ReportConfiguration.by_domain(user.domain)
        if not reports:
            return []

        root = ElementTree.Element('fixture', attrib={'id': self.id})
        reports_elem = ElementTree.Element('reports')
        for report in reports:
            reports_elem.append(self._report_to_fixture(report))
        root.append(reports_elem)
        return [root]

    def _report_to_fixture(self, report):
        report_elem = ElementTree.Element('report', attrib={'id': report._id})
        report_elem.append(self._element('name', report.title))
        report_elem.append(self._element('description', report.description))
        # todo: set filter values properly?
        data_source = ReportFactory.from_spec(report)

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
