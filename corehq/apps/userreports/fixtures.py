import json
from xml.etree import ElementTree
from corehq import toggles
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.reports.specs import MultibarChartSpec
from .models import ReportConfiguration


def report_fixture_generator(user, version, last_sync=None):
    """
    Generates a report fixture for mobile that can be used by a report module
    """
    if not toggles.MOBILE_UCR.enabled(user.domain):
        return []

    reports = ReportConfiguration.by_domain(user.domain)
    if not reports:
        return []

    root = ElementTree.Element('fixture', attrib={'id': 'commcare:reports'})
    reports_elem = ElementTree.Element('reports')
    for report in reports:
        reports_elem.append(_report_to_fixture(report))
    root.append(reports_elem)
    return [root]


def _report_to_fixture(report):
    report_elem = ElementTree.Element('report',
        attrib={
            'id': report._id,
        },
    )
    report_elem.append(_element('name', report.title))
    report_elem.append(_element('description', report.description))
    # todo: set filter values properly?
    data_source = ReportFactory.from_spec(report)

    rows_elem = ElementTree.Element('rows')

    for i, row in enumerate(data_source.get_data()):
        row_elem = ElementTree.Element('row', attrib={'index': str(i)})
        for k in sorted(row.keys()):
            row_elem.append(_element('column', _serialize(row[k]), attrib={'id': k}))
        rows_elem.append(row_elem)

    report_elem.append(rows_elem)
    return report_elem


def _element(name, text, attrib=None):
    attrib = attrib or {}
    element = ElementTree.Element(name, attrib=attrib)
    element.text = text
    return element


def _serialize(value):
    # todo: be smarter than this
    return '' if value is None else unicode(value)
