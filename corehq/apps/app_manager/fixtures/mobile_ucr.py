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
            filter_slug: filter for filter_slug, filter in all_filter_values.items()
            if filter is not None
        }
        defer_filters = {
            filter_slug: filter for filter_slug, filter in all_filter_values.items()
            if filter is None
        }
        data_source.set_filter_values(filter_values)
        data_source.defer_filters(defer_filters)

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
