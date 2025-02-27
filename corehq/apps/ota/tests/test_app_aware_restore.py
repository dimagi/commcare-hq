from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from django.test import TestCase

from casexml.apps.case.xml import V3
from casexml.apps.phone.models import SimplifiedSyncLog
from casexml.apps.phone.tests.utils import (
    call_fixture_generator,
    create_restore_user,
)
from casexml.apps.phone.utils import MockDevice

from corehq import toggles
from corehq.apps.app_manager.fixtures.mobile_ucr import (
    ReportFixturesProviderV2,
    report_fixture_generator,
)
from corehq.apps.app_manager.models import (
    Application,
    ReportAppConfig,
    ReportModule,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.reports.data_source import (
    ConfigurableReportDataSource,
)
from corehq.apps.userreports.tests.utils import (
    get_sample_report_config,
    mock_datasource_config,
)
from corehq.apps.users.dbaccessors import delete_all_users


class AppAwareSyncTests(TestCase):
    domain = 'test_domain'
    rows = [{
        'owner': 'bob',
        'count': 3,
        'is_starred': True
    }]

    @classmethod
    def setUpClass(cls):
        super(AppAwareSyncTests, cls).setUpClass()
        delete_all_users()
        cls.domain_obj = create_domain(cls.domain)
        toggles.MOBILE_UCR.set(cls.domain, True, toggles.NAMESPACE_DOMAIN)
        cls.user = create_restore_user(cls.domain)

        cls.app1 = Application.new_app(cls.domain, 'Test App 1')
        cls.report_config1 = get_sample_report_config()
        cls.report_config1.domain = cls.domain
        cls.report_config1.save()
        report_app_config = {
            'report_id': cls.report_config1.get_id,
            'uuid': '123456'
        }
        module = cls.app1.add_module(ReportModule.new_module('Reports', None))
        module.report_configs = [ReportAppConfig.wrap(report_app_config)]
        cls.app1.save()

        cls.app2 = Application.new_app(cls.domain, 'Test App 2')
        cls.report_config2 = get_sample_report_config()
        cls.report_config2.domain = cls.domain
        cls.report_config2.save()
        report_app_config = {
            'report_id': cls.report_config2.get_id,
            'uuid': 'abcdef'
        }
        module = cls.app2.add_module(ReportModule.new_module('Reports', None))
        module.report_configs = [ReportAppConfig.wrap(report_app_config)]
        cls.app2.save()

        cls.app3 = Application.new_app(cls.domain, 'Test App 3')
        cls.app3.save()

    @classmethod
    def tearDownClass(cls):
        toggles.MOBILE_UCR.set(cls.domain, False, toggles.NAMESPACE_DOMAIN)
        cls.app1.delete()
        cls.report_config1.delete()
        cls.app2.delete()
        cls.report_config2.delete()
        delete_all_users()
        domain = Domain.get_by_name(cls.domain)
        domain.delete()
        super(AppAwareSyncTests, cls).tearDownClass()

    def _get_fixtures_by_prefix(self, fixtures, fixture_id_prefix):
        return [f for f in fixtures if f.attrib.get('id').startswith(fixture_id_prefix)]

    def _expected_v2_report_fixtures_for_id(self, report_id):
        return {
            f'{ReportFixturesProviderV2.id}:index',
            f'{ReportFixturesProviderV2.id}:{report_id}',
            f'{ReportFixturesProviderV2.id}-filters:{report_id}',
        }

    def test_report_fixtures_provider_without_app(self):
        """
        ReportFixturesProvider should iterate all apps if app not given
        """
        with patch.object(ConfigurableReportDataSource, 'get_data') as get_data_mock:
            get_data_mock.return_value = self.rows
            with mock_datasource_config():
                fixtures = call_fixture_generator(report_fixture_generator, self.user)
                v2_report_fixtures = self._get_fixtures_by_prefix(fixtures, ReportFixturesProviderV2.id)
        self.assertEqual(len(v2_report_fixtures), 5)
        report_ids = {r.attrib.get('id') for r in v2_report_fixtures}
        self.assertEqual(
            report_ids,
            self._expected_v2_report_fixtures_for_id('123456') | self._expected_v2_report_fixtures_for_id('abcdef')
        )

    def test_report_fixtures_provider_with_app(self):
        """
        ReportFixturesProvider should not iterate all apps if app given
        """

        with patch.object(ConfigurableReportDataSource, 'get_data') as get_data_mock:
            get_data_mock.return_value = self.rows
            with mock_datasource_config():
                fixtures = call_fixture_generator(report_fixture_generator, self.user, app=self.app1)
                v2_report_fixtures = self._get_fixtures_by_prefix(fixtures, ReportFixturesProviderV2.id)

        self.assertEqual(len(v2_report_fixtures), 3)
        report_ids = {r.attrib.get('id') for r in v2_report_fixtures}
        self.assertEqual(report_ids, self._expected_v2_report_fixtures_for_id('123456'))

    def test_default_mobile_ucr_sync_interval(self):
        """
        When sync interval is set, ReportFixturesProvider should provide reports only if
        the interval has passed since the last sync or a new build is being requested.
        """
        with patch.object(ConfigurableReportDataSource, 'get_data') as get_data_mock:
            get_data_mock.return_value = self.rows
            with mock_datasource_config():
                self.domain_obj.default_mobile_ucr_sync_interval = 4   # hours
                two_hours_ago = datetime.utcnow() - timedelta(hours=2)
                recent_sync = SimplifiedSyncLog(
                    domain=self.domain_obj.name,
                    date=two_hours_ago,
                    user_id='456',
                    build_id=self.app1.get_id,
                )
                recent_sync.save()
                fixtures = call_fixture_generator(report_fixture_generator, self.user, app=self.app1,
                                                  last_sync=recent_sync, project=self.domain_obj,
                                                  current_sync_log=Mock())
                v2_report_fixtures = self._get_fixtures_by_prefix(fixtures, ReportFixturesProviderV2.id)
                self.assertEqual(len(v2_report_fixtures), 0)

                recent_sync_new_build = SimplifiedSyncLog(
                    domain=self.domain_obj.name,
                    date=two_hours_ago,
                    user_id='456',
                    build_id='123',
                )
                recent_sync_new_build.save()
                fixtures = call_fixture_generator(report_fixture_generator, self.user, app=self.app1,
                                                  last_sync=recent_sync_new_build, project=self.domain_obj,
                                                  current_sync_log=Mock())
                v2_report_fixtures = self._get_fixtures_by_prefix(fixtures, ReportFixturesProviderV2.id)
                self.assertEqual(len(v2_report_fixtures), 3)
                report_ids = {r.attrib.get('id') for r in v2_report_fixtures}
                self.assertEqual(report_ids, self._expected_v2_report_fixtures_for_id('123456'))
                self.domain_obj.default_mobile_ucr_sync_interval = None

    def test_report_fixtures_provider_with_app_that_doesnt_have_reports(self):
        with patch.object(ConfigurableReportDataSource, 'get_data') as get_data_mock:
            get_data_mock.return_value = self.rows
            fixtures = call_fixture_generator(report_fixture_generator, self.user, app=self.app3)
        self.assertEqual(len(list(fixtures)), 0)

    def test_user_restore(self):
        with patch.object(ConfigurableReportDataSource, 'get_data') as get_data_mock:
            get_data_mock.return_value = self.rows
            with mock_datasource_config():
                device = MockDevice(self.domain_obj, self.user)
                restore = device.sync(version=V3).payload.decode('utf-8')
                self.assertIn('<fixture id="commcare:reports"', restore)
                self.assertIn('report_id="{id}"'.format(id=self.report_config1._id), restore)
                self.assertIn('report_id="{id}"'.format(id=self.report_config2._id), restore)
