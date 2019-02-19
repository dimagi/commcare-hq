from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from mock import patch

from corehq.util.test_utils import flag_enabled
from casexml.apps.phone.tests.utils import create_restore_user, call_fixture_generator
from corehq import toggles
from corehq.apps.app_manager.fixtures.mobile_ucr import report_fixture_generator
from corehq.apps.app_manager.models import Application, ReportModule, ReportAppConfig
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.tests.utils import (
    get_sample_report_config, mock_datasource_config
)
from corehq.apps.users.models import UserRole, Permissions


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

    def test_report_fixtures_provider_without_app(self):
        """
        ReportFixturesProvider should iterate all apps if app not given
        """
        from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
        with patch.object(ConfigurableReportDataSource, 'get_data') as get_data_mock:
            get_data_mock.return_value = self.rows
            with mock_datasource_config():
                fixtures = call_fixture_generator(report_fixture_generator, self.user)
        reports = fixtures[0].findall('.//report')
        self.assertEqual(len(reports), 2)
        report_ids = {r.attrib.get('id') for r in reports}
        self.assertEqual(report_ids, {'123456', 'abcdef'})

    def test_report_fixtures_provider_with_app(self):
        """
        ReportFixturesProvider should not iterate all apps if app given
        """
        from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
        with patch.object(ConfigurableReportDataSource, 'get_data') as get_data_mock:
            get_data_mock.return_value = self.rows
            with mock_datasource_config():
                fixtures = call_fixture_generator(report_fixture_generator, self.user, app=self.app1)
        reports = fixtures[0].findall('.//report')
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].attrib.get('id'), '123456')

    @flag_enabled('ROLE_WEBAPPS_PERMISSIONS')
    def test_report_fixtures_provider_with_cloudcare(self):
        """
        ReportFixturesProvider should iterate only allowed apps if sync is from cloudcare
        """
        from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
        role = UserRole(
            domain=self.domain,
            permissions=Permissions(
                view_web_apps=False,
                view_web_apps_list=[self.app1._id]
            ),
            name='WebApp Restricted'
        )
        role.save()
        self.user._couch_user.set_role(self.domain, role.get_qualified_id())

        with patch.object(ConfigurableReportDataSource, 'get_data') as get_data_mock:
            get_data_mock.return_value = self.rows
            with mock_datasource_config():
                fixtures = call_fixture_generator(
                    report_fixture_generator,
                    self.user,
                    device_id="WebAppsLogin|user@project.commcarehq.org"
                )
        reports = fixtures[0].findall('.//report')
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].attrib.get('id'), '123456')

    def test_report_fixtures_provider_with_app_that_doesnt_have_reports(self):
        from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
        with patch.object(ConfigurableReportDataSource, 'get_data') as get_data_mock:
            get_data_mock.return_value = self.rows
            fixtures = call_fixture_generator(report_fixture_generator, self.user, app=self.app3)
        self.assertEqual(len(fixtures), 0)

    def test_user_restore(self):
        from casexml.apps.phone.utils import MockDevice
        from casexml.apps.case.xml import V3
        from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource

        with patch.object(ConfigurableReportDataSource, 'get_data') as get_data_mock:
            get_data_mock.return_value = self.rows
            with mock_datasource_config():
                device = MockDevice(self.domain_obj, self.user)
                restore = device.sync(version=V3).payload.decode('utf-8')
                self.assertIn('<fixture id="commcare:reports"', restore)
                self.assertIn('report_id="{id}"'.format(id=self.report_config1._id), restore)
                self.assertIn('report_id="{id}"'.format(id=self.report_config2._id), restore)
