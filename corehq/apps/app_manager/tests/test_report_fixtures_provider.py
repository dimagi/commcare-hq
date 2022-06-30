from datetime import datetime

from django.test import SimpleTestCase

from lxml import etree
from lxml.builder import E
from unittest.mock import Mock, patch

from casexml.apps.phone.models import UCRSyncLog

from corehq.apps.app_manager.fixtures.mobile_ucr import (
    ReportDataCache,
    ReportFixturesProviderV1,
    ReportFixturesProviderV2,
    _get_report_index_fixture,
)
from corehq.apps.app_manager.models import (
    ReportAppConfig,
    StaticChoiceListFilter,
)
from corehq.apps.app_manager.tests.test_report_config import (
    MAKE_REPORT_CONFIG,
    mock_report_configuration_get,
)
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.util.test_utils import flag_enabled


@flag_enabled('ADD_ROW_INDEX_TO_MOBILE_UCRS')
class ReportFixturesProviderTests(SimpleTestCase, TestXmlMixin):

    file_path = ('data', 'fixtures')
    maxDiff = None
    @staticmethod
    def get_data_source_mock():
        data_source_mock = Mock()
        data_source_mock.get_data.return_value = [
            {'foo': 1, 'bar': 2, 'baz': 3},
            {'ham': 1, 'spam': 2, 'baz': 3},
        ]
        data_source_mock.has_total_row = False
        return data_source_mock

    def _test_report_fixtures_provider(self, provider, expected_filename, data_source=None):
        report_id = 'deadbeef'
        report_app_config = ReportAppConfig(
            uuid='c0ffee',
            report_id=report_id,
            filters={'computed_owner_name_40cc88a0_1': StaticChoiceListFilter()}
        )
        user = Mock(user_id='mock-user-id')

        with mock_report_configuration_get({report_id: MAKE_REPORT_CONFIG('test_domain', report_id)}), \
                patch('corehq.apps.app_manager.fixtures.mobile_ucr.ConfigurableReportDataSource') as report_datasource, \
                patch('corehq.apps.app_manager.fixtures.mobile_ucr._format_last_sync_time') as last_sync_time_patch:
            mock = data_source or self.get_data_source_mock()
            mock.has_total_row = False
            mock.total_column_ids = ['baz']
            report_datasource.from_spec.return_value = mock
            last_sync_time_patch.return_value = datetime(2017, 9, 11, 6, 35, 20).isoformat()
            fixtures = provider.report_config_to_fixture(report_app_config, user)
            report = E.restore()
            report.extend(fixtures)
            self.assertXMLEqual(
                etree.tostring(report, pretty_print=True, encoding='utf-8').decode('utf-8'),
                self.get_xml(expected_filename).decode('utf-8')
            )

    def test_v1_report_fixtures_provider(self):
        self._test_report_fixtures_provider(ReportFixturesProviderV1(), 'expected_v1_report')

    def test_v2_report_fixtures_provider(self):
        self._test_report_fixtures_provider(ReportFixturesProviderV2(), 'expected_v2_report')

    def test_report_fixtures_data_cache(self):
        data_source = self.get_data_source_mock()
        cache = ReportDataCache()
        self._test_report_fixtures_provider(ReportFixturesProviderV1(cache), 'expected_v1_report', data_source)
        self._test_report_fixtures_provider(ReportFixturesProviderV2(cache), 'expected_v2_report', data_source)
        data_source.get_data.assert_called_once()

    def test_v2_report_fixtures_provider_iterative_total_row(self):
        report_id = 'deadbeef'
        provider = ReportFixturesProviderV2()
        report_app_config = ReportAppConfig(
            uuid='c0ffee',
            report_id=report_id,
            filters={'computed_owner_name_40cc88a0_1': StaticChoiceListFilter()}
        )
        user = Mock(user_id='mock-user-id')

        with mock_report_configuration_get({report_id: MAKE_REPORT_CONFIG('test_domain', report_id)}), \
             patch(
                 'corehq.apps.app_manager.fixtures.mobile_ucr.ConfigurableReportDataSource') as report_datasource, \
            patch('corehq.apps.app_manager.fixtures.mobile_ucr._format_last_sync_time') as last_sync_time_patch:
            mock = self.get_data_source_mock()
            mock.has_total_row = True
            mock.total_column_ids = ['baz']
            mock.final_column_ids = ['foo', 'bar', 'baz']
            report_datasource.from_spec.return_value = mock
            last_sync_time_patch.return_value = datetime(2017, 9, 11, 6, 35, 20).isoformat()
            fixtures = provider.report_config_to_fixture(report_app_config, user)
            report = E.restore()
            report.extend(fixtures)
            self.assertXMLEqual(
                etree.tostring(report, pretty_print=True, encoding='utf-8').decode('utf-8'),
                self.get_xml('expected_v2_report_total').decode('utf-8')
            )

    def test_v2_report_fixtures_provider_caching(self):
        report_id = 'deadbeef'
        provider = ReportFixturesProviderV2()
        report_app_config = ReportAppConfig(
            uuid='c0ffee',
            report_id=report_id,
            filters={'computed_owner_name_40cc88a0_1': StaticChoiceListFilter()},
            sync_delay=1.0,
        )
        restore_user = Mock(user_id='mock-user-id')
        restore_state = Mock(
            overwrite_cache=False,
            restore_user=restore_user,
            last_sync_log=Mock(last_ucr_sync_times=()),
        )

        with mock_report_configuration_get({report_id: MAKE_REPORT_CONFIG('test_domain', report_id)}), \
                patch('corehq.apps.app_manager.fixtures.mobile_ucr.ConfigurableReportDataSource') as report_datasource, \
                patch('corehq.apps.app_manager.fixtures.mobile_ucr._utcnow') as utcnow_patch:

            report_datasource.from_spec.return_value = self.get_data_source_mock()
            utcnow_patch.return_value = datetime(2017, 9, 11, 6, 35, 20)
            configs = provider._relevant_report_configs(restore_state, [report_app_config])
            self.assertEqual(configs, ([report_app_config], set()))

            restore_state = Mock(
                overwrite_cache=False,
                restore_user=restore_user,
                last_sync_log=Mock(last_ucr_sync_times=(
                    UCRSyncLog(report_uuid=report_app_config.uuid, datetime=datetime.utcnow()),
                )),
            )

            configs = provider._relevant_report_configs(restore_state, [report_app_config])
            self.assertEqual(configs, ([], set()))

            configs = provider._relevant_report_configs(restore_state, [])
            self.assertEqual(configs, ([], {report_app_config.uuid}))

    @patch('corehq.apps.app_manager.fixtures.mobile_ucr._format_last_sync_time')
    def test_get_report_index_fixture(self, last_sync_time_patch):
        last_sync_time_patch.return_value = datetime(2017, 9, 11, 6, 35, 20).isoformat()
        restore_user = Mock(domain='mock-domain', user_id='mock-user-id')
        report_index_fixture = _get_report_index_fixture(restore_user)
        self.assertXMLEqual(
            etree.tostring(report_index_fixture, pretty_print=True, encoding='utf-8').decode('utf-8'),
            """
            <fixture id="commcare-reports:index" user_id="mock-user-id">
              <report_index>
                <reports last_update="2017-09-11T06:35:20"/>
              </report_index>
            </fixture>
            """
        )

    def _test_get_oldest_sync_time(self, utcnow, synced_ids, purged_ids, expected):
        sync_log = Mock()
        sync_log.last_ucr_sync_times = [
            Mock(report_uuid='a', datetime=datetime(2018, 9, 11, 6, 35, 20)),
            Mock(report_uuid='b', datetime=datetime(2017, 9, 11, 6, 35, 20))
        ]
        restore_state = Mock()
        restore_state.last_sync_log = sync_log
        restore_state.overwrite_cache = False
        synced_fixtures = [
            Mock(uuid=_id) for _id in synced_ids
        ]
        with patch('corehq.apps.app_manager.fixtures.mobile_ucr._utcnow') as utcnow_patch:
            utcnow_patch.return_value = utcnow
            oldest_sync_time = ReportFixturesProviderV2._get_oldest_sync_time(
                restore_state, synced_fixtures, purged_ids
            )
        self.assertEqual(oldest_sync_time, expected)

    def test_get_oldest_sync_time_all_sync(self):
        utcnow = datetime.utcnow()
        self._test_get_oldest_sync_time(utcnow, ['a', 'b'], set(), utcnow)

    def test_get_oldest_sync_time_old(self):
        self._test_get_oldest_sync_time(datetime.utcnow(), ['c'], set(), datetime(2017, 9, 11, 6, 35, 20))

    def test_get_oldest_sync_time_excluded(self):
        self._test_get_oldest_sync_time(datetime.utcnow(), ['c'], {'b'}, datetime(2018, 9, 11, 6, 35, 20))
