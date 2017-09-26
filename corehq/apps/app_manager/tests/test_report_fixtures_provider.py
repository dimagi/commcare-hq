from datetime import datetime
from lxml import etree
from lxml.builder import E
from django.test import SimpleTestCase
from mock import Mock, patch
from corehq.apps.app_manager.fixtures.mobile_ucr import (
    ReportFixturesProvider, ReportFixturesProviderV2
)
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

    def test_v1_report_fixtures_provider(self):
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
            report = provider.report_config_to_v1_fixture(report_app_config, user)
            self.assertEqual(
                etree.tostring(report, pretty_print=True),
                self.get_xml('expected_report')
            )

    def test_v2_report_fixtures_provider(self):
        report_id = 'deadbeef'
        provider = ReportFixturesProviderV2()
        report_app_config = ReportAppConfig(
            uuid='c0ffee',
            report_id=report_id,
            filters={'computed_owner_name_40cc88a0_1': StaticChoiceListFilter()}
        )
        user = Mock(user_id='mock-user-id')

        with mock_report_configuration_get({report_id: MAKE_REPORT_CONFIG('test_domain', report_id)}), \
                patch('corehq.apps.app_manager.fixtures.mobile_ucr.ReportFactory') as report_factory_patch, \
                patch('corehq.apps.app_manager.fixtures.mobile_ucr._utcnow') as utcnow_patch:

            report_factory_patch.from_spec.return_value = self.get_data_source_mock()
            utcnow_patch.return_value = datetime(2017, 9, 11, 6, 35, 20)
            fixtures = provider.report_config_to_v2_fixture(report_app_config, user)
            report = E.restore()
            report.extend(fixtures)
            self.assertXMLEqual(
                etree.tostring(report, pretty_print=True),
                self.get_xml('expected_v2_report')
            )
