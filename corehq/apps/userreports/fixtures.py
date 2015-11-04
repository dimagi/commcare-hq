from datetime import datetime
import logging
from xml.etree import ElementTree

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.models import (
    Application,
    AutoFilter,
    CustomDataAutoFilter,
    ReportModule,
    StaticChoiceFilter,
    StaticChoiceListFilter,
    StaticDatespanFilter,
)
from corehq.apps.userreports.exceptions import UserReportsError
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.util import localize
from corehq.util.xml import serialize
from .models import ReportConfiguration


def wrap_by_filter_type(report_app_filter):
    doc_type_to_filter_class = {
        'AutoFilter': AutoFilter,
        'CustomDataAutoFilter': CustomDataAutoFilter,
        'StaticChoiceFilter': StaticChoiceFilter,
        'StaticChoiceListFilter': StaticChoiceListFilter,
        'StaticDatespanFilter': StaticDatespanFilter,
    }
    filter_class = doc_type_to_filter_class.get(report_app_filter.doc_type)
    if not filter_class:
        raise Exception("Unknown saved filter type: %s " % report_app_filter.doc_type)
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
                pass
            except Exception as err:
                logging.exception('Error generating report fixture: {}'.format(err))
        root.append(reports_elem)
        return [root]

    def _report_config_to_fixture(self, report_config, user):
        report_elem = ElementTree.Element('report', attrib={'id': report_config.uuid})
        report = ReportConfiguration.get(report_config.report_id)
        report_elem.append(self._element('name', localize(report_config.header, user.language)))
        report_elem.append(self._element('description', localize(report_config.description, user.language)))
        data_source = ReportFactory.from_spec(report)

        data_source.set_filter_values({
            filter_slug: wrap_by_filter_type(filter).get_filter_value(user)
            for filter_slug, filter in report_config.filters.items()
        })

        rows_elem = ElementTree.Element('rows')

        for i, row in enumerate(data_source.get_data()):
            row_elem = ElementTree.Element('row', attrib={'index': str(i)})
            for k in sorted(row.keys()):
                row_elem.append(self._element('column', serialize(row[k]), attrib={'id': k}))
            rows_elem.append(row_elem)

        report_elem.append(rows_elem)
        return report_elem

    @staticmethod
    def _element(name, text, attrib=None):
        attrib = attrib or {}
        element = ElementTree.Element(name, attrib=attrib)
        element.text = text
        return element

report_fixture_generator = ReportFixturesProvider()
