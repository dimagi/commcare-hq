from lxml import etree
from django.test import SimpleTestCase
from mock import Mock, patch
from corehq.apps.app_manager.fixtures.mobile_ucr import ReportFixturesProvider
from corehq.apps.app_manager.models import ReportAppConfig, StaticChoiceListFilter
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.tests.test_report_config import MAKE_REPORT_CONFIG, \
    mock_report_configuration_get


class ReportFixturesProviderTests(SimpleTestCase, TestXmlMixin):

    file_path = ('data', 'fixtures')

    @staticmethod
    def get_data_source_mock():
        data_source_mock = Mock()
        data_source_mock.get_data.return_value = [
            {'foo': 1, 'bar': 2, 'baz': 3},
            {'ham': 1, 'spam': 2, 'eggs': 3},
        ]
        data_source_mock.has_total_row = False
        return data_source_mock

    def test_report_fixtures_provider(self):
        report_id = 'deadbeef'
        provider = ReportFixturesProvider()
        report_app_config = ReportAppConfig(
            uuid='c0ffee',
            report_id=report_id,
            filters={'computed_owner_name_40cc88a0_1': StaticChoiceListFilter()}
        )
        user = Mock()

        with mock_report_configuration_get({report_id: MAKE_REPORT_CONFIG('test_domain', report_id)}), \
                patch('corehq.apps.app_manager.fixtures.mobile_ucr.ReportFactory') as report_factory_patch:

            report_factory_patch.from_spec.return_value = self.get_data_source_mock()
            report = provider.report_config_to_fixture(report_app_config, user)
            self.assertEqual(
                etree.tostring(report, pretty_print=True),
                self.get_xml('expected_report')
            )
