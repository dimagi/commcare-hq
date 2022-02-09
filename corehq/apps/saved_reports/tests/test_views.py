import json
from django.test import TestCase
from corehq.apps.saved_reports.models import (
    ReportConfig,
    ReportNotification,
)
from corehq.apps.reports.views import (
    MySavedReportsView,
    AddSavedReportConfigView,
)
from corehq.apps.users.models import WebUser
from corehq.apps.domain.shortcuts import create_domain
from django.urls.base import reverse
from unittest.mock import patch


class TestDomainSharedConfigs(TestCase):
    DOMAIN = 'test_domain'
    OWNER_ID = '5'

    def test_domain_does_not_have_shared_configs(self):
        self.assertEqual(ReportConfig.shared_on_domain(self.DOMAIN), [])

    def test_domain_has_shared_configs(self):
        config = ReportConfig(domain=self.DOMAIN, owner_id=self.OWNER_ID)
        config.save()
        self.addCleanup(config.delete)

        self._create_report(
            domain=self.DOMAIN,
            owner_id=self.OWNER_ID,
            config_ids=[config._id],
        )
        configs = ReportConfig.shared_on_domain(self.DOMAIN, stale=False)

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]._id, config._id)

    def test_config_used_in_multiple_report_notifications(self):
        config = ReportConfig(domain=self.DOMAIN, owner_id=self.OWNER_ID)
        config.save()
        self.addCleanup(config.delete)

        self._create_report(
            domain=self.DOMAIN,
            owner_id=self.OWNER_ID,
            config_ids=[config._id],
        )
        self._create_report(
            domain=self.DOMAIN,
            owner_id=self.OWNER_ID,
            config_ids=[config._id],
        )

        configs = ReportConfig.shared_on_domain(self.DOMAIN, stale=False)
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]._id, config._id)

    def _create_report(self, domain=None, owner_id=None, config_ids=[]):
        report = ReportNotification(domain=domain, owner_id=owner_id, config_ids=config_ids)
        report.save()
        self.addCleanup(report.delete)
        return report


class TestReportsBase(TestCase):

    DOMAIN = 'test-domain'
    DEFAULT_USER_PASSWORD = 'password'

    @classmethod
    def setUpClass(cls):
        super(TestReportsBase, cls).setUpClass()

        cls.domain_obj = create_domain(cls.DOMAIN)
        cls.admin_user = WebUser.create(
            cls.DOMAIN, 'username@test.com', cls.DEFAULT_USER_PASSWORD, None, None, is_admin=True
        )
        cls.other_admin_user = WebUser.create(
            cls.DOMAIN, 'username2@test.com', cls.DEFAULT_USER_PASSWORD, None, None, is_admin=True
        )
        cls.non_admin_user = WebUser.create(
            cls.DOMAIN, 'username3@test.com', cls.DEFAULT_USER_PASSWORD, None, None, is_admin=False
        )

    @classmethod
    def tearDownClass(cls):
        cls.admin_user.delete(cls.DOMAIN, deleted_by=None)
        cls.other_admin_user.delete(cls.DOMAIN, deleted_by=None)
        cls.non_admin_user.delete(cls.DOMAIN, deleted_by=None)

        cls.domain_obj.delete()
        super(TestReportsBase, cls).tearDownClass()

    def create_report_notification(self, configs, owner_id):
        domain = configs[0].domain
        config_ids = [c._id for c in configs]
        rn = ReportNotification(
            domain=domain,
            config_ids=config_ids,
            owner_id=owner_id,
            interval='daily',
        )
        rn.save()
        self.addCleanup(rn.delete)
        return rn

    def create_report_config(self, domain, owner_id, **kwargs):
        rc = ReportConfig(domain=domain, owner_id=owner_id, **kwargs)
        rc.save()
        self.addCleanup(rc.delete)
        return rc

    def login_user(self, username):
        self.client.login(username=username, password=self.DEFAULT_USER_PASSWORD)


class TestMySavedReportsView(TestReportsBase):

    URL = reverse(MySavedReportsView.urlname, args=[TestReportsBase.DOMAIN])

    def shared_saved_reports_for_user(self, username):
        self.login_user(username)
        response = self.client.get(self.URL)
        return response.context['shared_saved_reports']

    @patch('corehq.apps.reports.views.user_can_view_reports', return_value=True)
    def test_one_admin_has_report_notifications(self, *args):
        config1 = self.create_report_config(domain=self.DOMAIN, owner_id=self.admin_user._id)
        config2 = self.create_report_config(domain=self.DOMAIN, owner_id=self.admin_user._id)
        config3 = self.create_report_config(domain=self.DOMAIN, owner_id=self.admin_user._id)
        self.create_report_notification([config1, config2], owner_id=self.admin_user._id)

        shared_reports = self.shared_saved_reports_for_user(self.admin_user.username)
        self.assertEqual(len(shared_reports), 2)

        config_ids = [r['_id'] for r in shared_reports]
        self.assertNotIn(config3._id, config_ids)

    @patch('corehq.apps.reports.views.user_can_view_reports', return_value=True)
    def test_multiple_admins_can_see_shared_reports(self, *args):
        config1 = self.create_report_config(domain=self.DOMAIN, owner_id=self.admin_user._id)
        _config2 = self.create_report_config(domain=self.DOMAIN, owner_id=self.other_admin_user._id)

        # Test scenario when only one admin user create a ReportNotification
        self.create_report_notification([config1], owner_id=self.admin_user._id)

        shared_reports = self.shared_saved_reports_for_user(self.admin_user.username)

        self.assertEqual(len(shared_reports), 1)
        self.assertEqual(shared_reports[0]['_id'], config1._id)

        # Other admin user should also see config1
        other_admin_shared_reports = self.shared_saved_reports_for_user(self.other_admin_user.username)

        self.assertEqual(len(other_admin_shared_reports), 1)
        self.assertEqual(other_admin_shared_reports[0]['_id'], config1._id)

    @patch('corehq.apps.reports.views.user_can_view_reports', return_value=True)
    def test_non_admin_can_see_only_own_shared_reports(self, *args):
        admin_config = self.create_report_config(domain=self.DOMAIN, owner_id=self.admin_user._id)
        non_admin_config = self.create_report_config(domain=self.DOMAIN, owner_id=self.non_admin_user._id)

        self.create_report_notification([admin_config], owner_id=self.admin_user._id)
        self.create_report_notification([non_admin_config], owner_id=self.non_admin_user._id)

        # Admin user should see both configs
        shared_reports = self.shared_saved_reports_for_user(self.admin_user.username)

        self.assertEqual(len(shared_reports), 2)

        # Non admin user should see only own config
        shared_reports = self.shared_saved_reports_for_user(self.non_admin_user.username)

        self.assertEqual(len(shared_reports), 1)
        self.assertEqual(shared_reports[0]['_id'], non_admin_config._id)


class TestAddSavedReportConfigView(TestReportsBase):

    URL = reverse(AddSavedReportConfigView.name, kwargs={'domain': TestReportsBase.DOMAIN})

    @patch('corehq.apps.reports.views.user_can_view_reports', return_value=True)
    def test_admin_can_edit_normal_config(self, *args):
        config1 = self.create_report_config(
            domain=self.DOMAIN,
            owner_id=self.admin_user._id,
            name='Name',
            description='',
        )

        new_description = 'This is a description'
        post_data = {
            'description': new_description,
            'name': config1.name,
            '_id': config1._id,
        }

        self.login_user(self.admin_user.username)
        response = self.client.post(
            self.URL,
            json.dumps(post_data),
            content_type='application/json;charset=UTF-8',
        )
        self.assertEqual(response.status_code, 200)

        updated_config = ReportConfig.get(config1._id)
        self.assertTrue(updated_config.description, new_description)

    @patch('corehq.apps.reports.views.user_can_view_reports', return_value=True)
    def test_another_admin_cannot_edit_normal_config(self, *args):
        config1 = self.create_report_config(
            domain=self.DOMAIN,
            owner_id=self.admin_user._id,
            name='Name',
            description='',
        )

        post_data = {
            'description': 'Malicious description',
            'name': config1.name,
            '_id': config1._id,
        }

        self.login_user(self.other_admin_user.username)
        try:
            _response = self.client.post(
                self.URL,
                json.dumps(post_data),
                content_type='application/json;charset=UTF-8',
            )
        except Exception as e:
            self.assertTrue(e.__class__ == AssertionError)

        # Validate that config1 is untouched
        original_config = ReportConfig.get(config1._id)
        self.assertEqual(original_config.description, '')

    @patch('corehq.apps.reports.views.user_can_view_reports', return_value=True)
    def test_other_admin_can_edit_shared_saved_report(self, *args):
        config1 = self.create_report_config(
            domain=self.DOMAIN,
            owner_id=self.admin_user._id,
            name='Name',
            description='',
        )
        # Create ReportNotification as to make confi1 shared
        self.create_report_notification([config1], owner_id=self.admin_user._id)

        new_description = 'This is a description'
        post_data = {
            'description': new_description,
            'name': config1.name,
            '_id': config1._id,
        }

        self.login_user(self.admin_user.username)
        response = self.client.post(
            self.URL,
            json.dumps(post_data),
            content_type='application/json;charset=UTF-8',
        )
        self.assertEqual(response.status_code, 200)

        updated_config = ReportConfig.get(config1._id)
        self.assertTrue(updated_config.description, new_description)

    def test_non_admin_cannot_edit_other_shared_configs(self):
        config1 = self.create_report_config(
            domain=self.DOMAIN,
            owner_id=self.admin_user._id,
            name='Name',
            description='',
        )

        post_data = {
            'description': 'Malicious description',
            'name': config1.name,
            '_id': config1._id,
        }

        self.login_user(self.non_admin_user.username)
        try:
            _response = self.client.post(
                self.URL,
                json.dumps(post_data),
                content_type='application/json;charset=UTF-8',
            )
        except Exception as e:
            self.assertTrue(e.__class__ == AssertionError)

        # Validate that config1 is untouched
        original_config = ReportConfig.get(config1._id)
        self.assertEqual(original_config.description, '')
