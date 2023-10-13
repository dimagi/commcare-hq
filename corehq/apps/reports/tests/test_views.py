import io
import json
import unittest
from couchdbkit import ResourceNotFound
from django.http import QueryDict
from django.http.response import Http404
from django.core.exceptions import PermissionDenied
from django.test import TestCase, RequestFactory
from unittest.mock import patch
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.apps.saved_reports.models import ReportConfig, ReportNotification
from corehq.blobs import get_blob_db
from corehq.apps.reports.views import (
    MySavedReportsView,
    AddSavedReportConfigView,
    soft_shift_to_domain_timezone,
    soft_shift_to_server_timezone,
)
from django.urls.base import reverse
from .. import views

from django.http import HttpRequest


REPORT_NAME_LOOKUP = {
    'worker_activity': 'corehq.apps.reports.standard.monitoring.WorkerActivityReport'
}


class TestEmailReport(TestCase):
    ARG_INDEX = 0
    RECIPIENT_INDEX = 0

    @patch.object(views, 'send_email_report')
    def test_user_can_send_email(self, mock_send_email):
        self._set_user_report_access(REPORT_NAME_LOOKUP['worker_activity'])
        response = self.email_report(report_name='worker_activity')
        mock_send_email.delay.assert_called_once()
        self.assertEqual(response.status_code, 200)

    @patch.object(views, 'send_email_report')
    def test_email_is_sent_to_recipient_list(self, mock_send_email):
        self.request = self._create_request(
            params=QueryDict('recipient_emails[]=user1@test.com&recipient_emails[]=user2@test.com'))
        self.email_report()

        self.assertEqual(
            mock_send_email.delay.call_args[self.ARG_INDEX][self.RECIPIENT_INDEX],
            {'user1@test.com', 'user2@test.com'}
        )

    @patch.object(views, 'send_email_report')
    def test_owner_flag_adds_owner_email_to_recipient_list(self, mock_send_email):
        # Setup creates a user with email address 'test_user@dimagi.com'
        self.request = self._create_request(params={
            'recipient_emails[]': 'user1@test.com',
            'send_to_owner': True
        })
        self.email_report()

        self.assertEqual(
            mock_send_email.delay.call_args[self.ARG_INDEX][self.RECIPIENT_INDEX],
            {'test_user@dimagi.com', 'user1@test.com'}
        )

    def test_invalid_form_returns_bad_request(self):
        invalid_form_params = {}
        self.request = self._create_request(params=invalid_form_params)
        response = self.email_report()
        self.assertEqual(response.status_code, 400)

    def test_invalid_slug_returns_404(self):
        with self.assertRaises(Http404):
            self.email_report(report_name='nonexistant_report')

    def test_when_user_cannot_view_report_receives_404(self):
        self._set_user_report_access('not_this_report')
        with self.assertRaises(Http404):
            self.email_report(report_name='worker_activity')

    def test_disallowed_request_get_method(self):
        self.request = self._create_request(method='get')
        response = self.email_report()
        self.assertEqual(response.status_code, 405)

# ################ Helpers / Setup
    def email_report(self, domain=None, report_name='worker_activity'):
        domain = domain or self.domain
        return views.email_report(self.request, domain, report_name, once=True)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()

        self.reports_role = UserRole.create(self.domain, 'Test Role', permissions=HqPermissions(
            view_report_list=[REPORT_NAME_LOOKUP['worker_activity']]
        ))

        self.user = WebUser.create(self.domain,
            'test_user@dimagi.com',
            'test_password',
            None,
            None,
            role_id=self.reports_role.get_id)

        self.user.is_authenticated = True
        self.request = self._create_request()

    def tearDown(self):
        self.user.delete(self.domain, deleted_by=None)
        self.reports_role.delete()

        super().tearDown()

    def _create_request(self, params=None, method='post'):
        if params is None:
            params = {'send_to_owner': True}

        # NOTE: The reason we're constructing an HttpRequest object here, rather than relying on RequestFactory,
        # is because some of our tests require duplicate keys. RequestFactory doesn't support the QueryDicts
        # that would be needed to represent those keys.
        request = HttpRequest()
        if method == 'get':
            request.GET.update(params)
            request.method = 'GET'
        else:
            request.POST.update(params)
            request.method = 'POST'

        request.user = self.user
        return request

    def _set_user_report_access(self, *report_names):
        self.reports_role.set_permissions(HqPermissions(view_report_list=list(report_names)).to_list())


class TestDeleteConfig(TestCase):
    def test_invalid_config_id_returns_404(self):
        with self.assertRaises(Http404):
            self.delete_config(config_id='nonexistant_config_id')

    def test_mismatched_domains_returns_404(self):
        report = self._create_saved_report(domain='not_your_domain')

        with self.assertRaises(Http404):
            self.delete_config(domain=self.domain, config_id=report._id)

    def test_non_owner_cannot_delete_saved_report(self):
        report = self._create_saved_report(user_id='not_you')

        with self.assertRaises(Http404):
            self.delete_config(config_id=report._id)

    def test_can_delete_saved_report(self):
        report = self._create_saved_report(domain=self.domain, user_id=self.user._id)

        response = self.delete_config(self.domain, report._id)
        self.assertEqual(response.status_code, 200)

        with self.assertRaises(ResourceNotFound):
            ReportConfig.get(report._id)

# ############ Helper / Setup
    def delete_config(self, domain=None, config_id='test'):
        domain = domain or self.domain
        return views.delete_config(self.request, domain, config_id)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.user = WebUser.create(cls.domain, 'test_user', 'test_password', None, None)
        cls.user.is_authenticated = True

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.request = self._create_request()

    def _create_request(self):
        url = f'/a/{self.domain}/deleteConfig'
        request = RequestFactory().delete(url)
        request.user = self.user
        return request

    def _create_saved_report(self, domain=None, user_id=None):
        config = ReportConfig(
            domain=domain or self.domain,
            owner_id=user_id or self.user._id,
            name='Test',
            description='Test Saved Report',
            report_slug='worker_activity',
            report_type='project_report'
        )
        config.save()
        self.addCleanup(config.delete)

        return config


class TestDeleteScheduledReport(TestCase):
    def test_invalid_report_redirects(self):
        response = self.delete_scheduled_report(report_id='invalid_report_id')
        self.assertEqual(response.status_code, 302)

    def test_mismatched_domains_returns_404(self):
        report = self._create_report(domain='not_your_domain')

        with self.assertRaises(Http404):
            self.delete_scheduled_report(domain=self.domain, report_id=report._id)

    def test_user_without_permissions_cannot_delete_report(self):
        report = self._create_report(owner_id='not_you')

        with self.assertRaises(Http404):
            self.delete_scheduled_report(user=self.user, report_id=report._id)

    @patch.object(views.messages, 'success')
    def test_owner_can_delete_report(self, mock_success):
        report = self._create_report(owner_id=self.user._id)

        response = self.delete_scheduled_report(user=self.user, report_id=report._id)
        self.assertEqual(response.status_code, 302)
        with self.assertRaises(ResourceNotFound):
            ReportNotification.get(report._id)

    @patch.object(views.messages, 'success')
    def test_domain_admin_can_delete_report(self, mock_success):
        domain_admin = self._create_user(username='domain_admin', is_admin=True)
        report = self._create_report(owner_id=self.user._id)

        response = self.delete_scheduled_report(user=domain_admin, report_id=report._id)
        self.assertEqual(response.status_code, 302)
        with self.assertRaises(ResourceNotFound):
            ReportNotification.get(report._id)

# ################## Helpers / Setup
    def delete_scheduled_report(self, user=None, domain=None, report_id='test_report'):
        if user:
            self.request.user = user

        domain = domain or self.domain
        return views.delete_scheduled_report(self.request, domain, report_id)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)

        cls.user = WebUser.create(cls.domain, 'test_user', 'test_password', None, None)
        cls.user.is_authenticated = True

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.request = self._create_request()

    def _create_user(self, username='test_user', is_admin=False):
        user = WebUser.create(self.domain, username, 'test_password', None, None, is_admin=is_admin)
        user.is_authenticated = True

        self.addCleanup(user.delete, deleted_by_domain=self.domain, deleted_by=None)
        return user

    def _create_request(self):
        url = f'/a/{self.domain}/delete_scheduled_report'
        request = RequestFactory().post(url)
        request.user = self.user
        return request

    def _create_report(self, domain=None, owner_id=None):
        domain = domain or self.domain
        owner_id = owner_id or self.user._id
        report = ReportNotification(domain=domain, owner_id=owner_id)
        report.save()
        self.addCleanup(report.delete)
        return report


class TestSendTestScheduledReport(TestCase):
    def test_invalid_report_raises_404(self):
        with self.assertRaises(Http404):
            self.send_scheduled_report('invalid_report_id')

    def test_mismatched_domains_returns_404(self):
        report = self._create_saved_report(domain='not_your_domain')

        with self.assertRaises(Http404):
            self.send_scheduled_report(report._id, domain=self.domain)

    @patch.object(views.messages, 'success')
    def test_owner_can_send_report(self, mock_success):
        report = self._create_saved_report(owner_id=self.user._id)

        response = self.send_scheduled_report(report._id, user=self.user)
        self.assertEqual(response.status_code, 302)

    @patch.object(views.messages, 'success')
    def test_domain_admin_can_send_report(self, mock_success):
        domain_admin = self._create_user(username='domain-admin', is_admin=True)

        report = self._create_saved_report(owner_id=self.user._id)

        response = self.send_scheduled_report(report._id, user=domain_admin)
        self.assertEqual(response.status_code, 302)

# ############## Helpers / Setup
    def send_scheduled_report(self, report_id, domain=None, user=None):
        if user:
            self.request.user = user

        domain = domain or self.domain
        return views.send_test_scheduled_report(self.request, domain, report_id)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)

        cls.user = WebUser.create(cls.domain, 'test_user', 'test_password', None, None)
        cls.user.is_authenticated = True

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.request = self._create_request()

    def _create_user(self, username='test_user', is_admin=False):
        user = WebUser.create(self.domain, username, 'test_password', None, None, is_admin=is_admin)
        user.is_authenticated = True

        self.addCleanup(user.delete, deleted_by_domain=self.domain, deleted_by=None)
        return user

    def _create_request(self):
        url = f'/a/{self.domain}/sendScheduledReport'
        request = RequestFactory().get(url)
        request.user = self.user
        return request

    def _create_saved_report(self, domain=None, owner_id=None):
        domain = domain or self.domain
        owner_id = owner_id or self.user._id
        report = ReportNotification(domain=domain, owner_id=owner_id)
        report.save()

        self.addCleanup(report.delete)
        return report


class TestExportReport(TestCase):
    def test_invalid_hash_returns_404(self):
        response = self.retrieve_exported_report(export_id='invalid_export_hash')
        self.assertEqual(response.status_code, 404)

    def test_mismatched_domain_returns_404(self):
        self._generate_report(domain='not_your_domain')

        with self.assertRaises(Http404):
            self.retrieve_exported_report(domain=self.domain)

    def test_user_lacking_permissions_returns_error(self):
        self._generate_report(report_name='my_report')
        self._set_user_report_access('not_this_report')

        with self.assertRaises(PermissionDenied):
            self.retrieve_exported_report()

    def test_authorized_user_can_retrieve_report(self):
        self._generate_report(report_name='my_report', content=b'Some File')
        self._set_user_report_access('my_report')

        response = self.retrieve_exported_report()
        self.assertEqual(response.content, b'Some File')

    def retrieve_exported_report(self, export_id=None, domain=None):
        if not export_id:
            export_id = self.export_id

        if not domain:
            domain = self.domain

        return views.export_report(self.request, domain, export_id, 'xlsx')

# ################ Helpers / Setup

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)

        cls.db = get_blob_db()

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()

        # Create a basic role for the user
        self.reports_role = UserRole.create(self.domain, 'Test Role', permissions=HqPermissions(
            view_report_list=[]
        ))

        self.user = WebUser.create(self.domain,
            'test_user',
            'test_password',
            None,
            None,
            role_id=self.reports_role.get_id)

        self.user.is_authenticated = True
        self.request = self._create_request()

        self.export_id = 'export_id'

    def tearDown(self):
        self.user.delete(self.domain, deleted_by=None)
        self.reports_role.delete()
        super().tearDown()

    def _create_request(self):
        url = f'/a/{self.domain}/exportReport'
        request = RequestFactory().get(url)
        request.user = self.user
        return request

    def _set_user_report_access(self, *report_names):
        # NOTE: user permissions get cached, so if these permissions
        # were changed between checks, the cache would need to be cleared
        self.reports_role.set_permissions(HqPermissions(view_report_list=list(report_names)).to_list())

    def _generate_report(self, export_id=None, report_name='test_report', domain=None, content=b'Some File'):
        export_id = export_id or self.export_id
        domain = domain or self.domain
        file = io.BytesIO(content)
        self.db.put(file,
            domain=domain,
            name='MyTestExport',
            parent_id=export_id,
            key=export_id,
            type_code=1,
            timeout=300,
            properties={'report_class': report_name})
        self.addCleanup(self.db.delete, export_id)


class TestViewScheduledReport(TestCase):
    def test_missing_report_returns_404(self):
        with self.assertRaises(Http404):
            self.view_scheduled_report('nonexistant_id')

    def test_mismatched_domains_returns_404(self):
        report = self._create_scheduled_report(domain='not_your_domain')

        with self.assertRaises(Http404):
            self.view_scheduled_report(report._id, domain=self.domain)

    def test_user_with_no_report_access_receives_404(self):
        self._set_user_report_access()  # Ensure the user has access to no reports
        # User should be unable to view even his own report
        scheduled_report = self._create_scheduled_report(owner_id=self.user._id)

        with self.assertRaises(Http404):
            self.view_scheduled_report(scheduled_report._id)

    def test_user_without_scheduled_report_access_recieves_404(self):
        scheduled_report = self._create_scheduled_report(owner_id='not_you')

        with self.assertRaises(Http404):
            self.view_scheduled_report(scheduled_report._id)

    def test_user_without_permissions_receives_error_message(self):
        saved_report = self._create_saved_report(user_id='not_you')
        scheduled_report = self._create_scheduled_report(config_ids=[saved_report._id])

        with self.assertRaises(Http404):
            self.view_scheduled_report(scheduled_report._id)

    @unittest.skip
    def test_can_view_scheduled_report(self):
        # TODO: Likely need to look into `send_to_elasticsarch`, especially in some existing
        # tests, to figure out how to populate elasticsearch so that the resulting report
        # can be generated
        saved_report = self._create_saved_report(slug='worker_activity')
        scheduled_report = self._create_scheduled_report(config_ids=[saved_report._id])

        self._set_user_report_access(REPORT_NAME_LOOKUP['worker_activity'])

        response = self.view_scheduled_report(scheduled_report._id)
        self.assertEqual(response.status_code, 200)

# ################### Helpers / Setup

    def view_scheduled_report(self, report_id, domain=None):
        domain = domain or self.domain
        return views.view_scheduled_report(self.request, domain, report_id)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.reports_role = UserRole.create(self.domain, 'Test Role', permissions=HqPermissions(
            view_report_list=[]
        ))
        self.user = WebUser.create(self.domain,
            'test_user',
            'test_password',
            None,
            None,
            role_id=self.reports_role.get_id)
        self.user.is_authenticated = True
        self.request = self._create_request()

    def tearDown(self):
        self.user.delete(self.domain, deleted_by=None)
        self.reports_role.delete()
        super().tearDown()

    def _create_request(self):
        url = f'/a/{self.domain}/view_scheduled_report'
        request = RequestFactory().get(url)
        request.user = self.user
        return request

    def _create_saved_report(self, domain=None, user_id=None, slug='worker_activity'):
        config = ReportConfig(
            domain=domain or self.domain,
            owner_id=user_id or self.user._id,
            name='Test',
            description='Test Saved Report',
            report_slug=slug,
            report_type='project_report'
        )
        config.save()
        self.addCleanup(config.delete)

        return config

    def _create_scheduled_report(self, domain=None, owner_id=None, config_ids=['fake']):
        domain = domain or self.domain
        owner_id = owner_id or self.user._id
        report = ReportNotification(domain=domain, owner_id=owner_id, config_ids=config_ids)
        report.save()
        self.addCleanup(report.delete)

        return report

    def _set_user_report_access(self, *report_names):
        # NOTE: user permissions get cached, so if these permissions
        # were changed between checks, the cache would need to be cleared
        self.reports_role.set_permissions(HqPermissions(view_report_list=list(report_names)).to_list())


class TestDomainSharedConfigs(TestCase):
    DOMAIN = 'test_domain'
    OWNER_ID = '5'

    def setUp(self) -> None:
        super().setUp()
        # Make sure cached value us cleared
        ReportConfig.shared_on_domain.clear(ReportConfig, domain=self.DOMAIN)

    def test_domain_does_not_have_shared_configs(self):
        self.assertEqual(len(ReportConfig.shared_on_domain(self.DOMAIN)), 0)

    def test_domain_has_shared_configs(self):
        config = ReportConfig(domain=self.DOMAIN, owner_id=self.OWNER_ID)
        config.save()
        self.addCleanup(config.delete)

        self._create_scheduled_report(
            domain=self.DOMAIN,
            owner_id=self.OWNER_ID,
            config_ids=[config._id],
        )
        # Clear cached value
        ReportConfig.shared_on_domain.clear(ReportConfig, domain=self.DOMAIN)

        configs = list(ReportConfig.shared_on_domain(self.DOMAIN))

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]._id, config._id)

    def test_config_used_in_multiple_report_notifications(self):
        config = ReportConfig(domain=self.DOMAIN, owner_id=self.OWNER_ID)
        config.save()
        self.addCleanup(config.delete)

        self._create_scheduled_report(
            domain=self.DOMAIN,
            owner_id=self.OWNER_ID,
            config_ids=[config._id],
        )
        self._create_scheduled_report(
            domain=self.DOMAIN,
            owner_id=self.OWNER_ID,
            config_ids=[config._id],
        )

        configs = list(ReportConfig.shared_on_domain(self.DOMAIN))
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]._id, config._id)

    def _create_scheduled_report(self, domain=None, owner_id=None, config_ids=[]):
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

    def log_user_in(self, username):
        self.client.login(username=username, password=self.DEFAULT_USER_PASSWORD)


class TestUserConfigsWithShared(TestReportsBase):

    def setUp(self) -> None:
        super().setUp()
        # Clear cached value
        ReportConfig.shared_on_domain.clear(ReportConfig, domain=self.DOMAIN)

    def test_no_shared_configs(self):
        config = self.create_report_config(self.DOMAIN, self.admin_user._id)
        configs = ReportConfig.by_domain_and_owner(
            self.DOMAIN,
            self.admin_user._id,
            include_shared=True,
            stale=False,
        )

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]._id, config._id)

    def test_with_shared_config(self):
        config = self.create_report_config(self.DOMAIN, self.admin_user._id)

        self.create_report_notification([config], owner_id=self.admin_user._id)
        # Clear cached value
        ReportConfig.shared_on_domain.clear(ReportConfig, domain=self.DOMAIN)

        configs = ReportConfig.by_domain_and_owner(
            self.DOMAIN,
            self.admin_user._id,
            include_shared=True,
            stale=False,
        )
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]._id, config._id)

    def test_with_other_owner_shared_config(self):
        self.create_report_config(self.DOMAIN, self.admin_user._id)
        config2 = self.create_report_config(self.DOMAIN, self.other_admin_user._id)
        self.create_report_notification([config2], owner_id=self.other_admin_user._id)

        configs = ReportConfig.by_domain_and_owner(
            self.DOMAIN,
            self.admin_user._id,
            include_shared=True,
            stale=False,
        )
        self.assertEqual(len(configs), 2)


class TestMySavedReportsView(TestReportsBase):

    URL = reverse(MySavedReportsView.urlname, args=[TestReportsBase.DOMAIN])

    def get_shared_saved_reports_for_user(self, username):
        ReportConfig.shared_on_domain.clear(ReportConfig, self.DOMAIN)

        self.log_user_in(username)
        response = self.client.get(self.URL)
        return response.context['shared_saved_reports']

    @patch('corehq.apps.reports.views.user_can_view_reports', return_value=True)
    def test_one_admin_has_report_notifications(self, *args):
        config1 = self.create_report_config(domain=self.DOMAIN, owner_id=self.admin_user._id)
        config2 = self.create_report_config(domain=self.DOMAIN, owner_id=self.admin_user._id)
        config3 = self.create_report_config(domain=self.DOMAIN, owner_id=self.admin_user._id)
        self.create_report_notification([config1, config2], owner_id=self.admin_user._id)

        shared_reports = self.get_shared_saved_reports_for_user(self.admin_user.username)
        self.assertEqual(len(shared_reports), 2)

        config_ids = [r['_id'] for r in shared_reports]
        self.assertNotIn(config3._id, config_ids)

    @patch('corehq.apps.reports.views.user_can_view_reports', return_value=True)
    def test_multiple_admins_can_see_shared_reports(self, *args):
        config1 = self.create_report_config(domain=self.DOMAIN, owner_id=self.admin_user._id)
        self.create_report_config(domain=self.DOMAIN, owner_id=self.other_admin_user._id)

        # Test scenario when only one admin user create a ReportNotification
        self.create_report_notification([config1], owner_id=self.admin_user._id)

        shared_reports = self.get_shared_saved_reports_for_user(self.admin_user.username)

        self.assertEqual(len(shared_reports), 1)
        self.assertEqual(shared_reports[0]['_id'], config1._id)

        # Other admin user should also see config1
        other_admin_shared_reports = self.get_shared_saved_reports_for_user(self.other_admin_user.username)

        self.assertEqual(len(other_admin_shared_reports), 1)
        self.assertEqual(other_admin_shared_reports[0]['_id'], config1._id)

    @patch('corehq.apps.reports.views.user_can_view_reports', return_value=True)
    def test_non_admin_can_see_only_own_shared_reports(self, *args):
        admin_config = self.create_report_config(domain=self.DOMAIN, owner_id=self.admin_user._id)
        non_admin_config = self.create_report_config(domain=self.DOMAIN, owner_id=self.non_admin_user._id)

        self.create_report_notification([admin_config], owner_id=self.admin_user._id)
        self.create_report_notification([non_admin_config], owner_id=self.non_admin_user._id)

        # Admin user should see both configs
        shared_reports = self.get_shared_saved_reports_for_user(self.admin_user.username)

        self.assertEqual(len(shared_reports), 2)

        # Non admin user should see only own config
        shared_reports = self.get_shared_saved_reports_for_user(self.non_admin_user.username)

        self.assertEqual(len(shared_reports), 1)
        self.assertEqual(shared_reports[0]['_id'], non_admin_config._id)


class TestAddSavedReportConfigView(TestReportsBase):

    URL = reverse(AddSavedReportConfigView.name, kwargs={'domain': TestReportsBase.DOMAIN})

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

        self.log_user_in(self.admin_user.username)
        response = self.client.post(
            self.URL,
            json.dumps(post_data),
            content_type='application/json;charset=UTF-8',
        )
        self.assertEqual(response.status_code, 200)

        updated_config = ReportConfig.get(config1._id)
        self.assertTrue(updated_config.description, new_description)

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

        self.log_user_in(self.other_admin_user.username)
        try:
            self.client.post(
                self.URL,
                json.dumps(post_data),
                content_type='application/json;charset=UTF-8',
            )
        except Exception as e:
            self.assertTrue(e.__class__ == AssertionError)

        # Validate that config1 is untouched
        original_config = ReportConfig.get(config1._id)
        self.assertEqual(original_config.description, '')

    def test_other_admin_can_edit_shared_saved_report(self, *args):
        config1 = self.create_report_config(
            domain=self.DOMAIN,
            owner_id=self.admin_user._id,
            name='Name',
            description='',
        )
        # Create ReportNotification as to make confi1 shared
        self.create_report_notification([config1], owner_id=self.admin_user._id)
        ReportConfig.shared_on_domain.clear(ReportConfig, self.DOMAIN, only_id=True)

        new_description = 'This is a description'
        post_data = {
            'description': new_description,
            'name': config1.name,
            '_id': config1._id,
        }

        self.log_user_in(self.other_admin_user.username)
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

        self.log_user_in(self.non_admin_user.username)
        try:
            self.client.post(
                self.URL,
                json.dumps(post_data),
                content_type='application/json;charset=UTF-8',
            )
        except Exception as e:
            self.assertTrue(e.__class__ == AssertionError)

        # Validate that config1 is untouched
        original_config = ReportConfig.get(config1._id)
        self.assertEqual(original_config.description, '')


class TestTimezoneConversion(TestCase):
    DOMAIN = "test-domain"

    @classmethod
    def setUpClass(cls) -> None:
        cls.domain_obj = create_domain(cls.DOMAIN)
        cls.domain_obj.default_timezone = "Pacific/Kiritimati"
        cls.domain_obj.save()
        super()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.domain_obj.delete()
        super()

    def test_convert_to_server_timezone(self):
        report_notification = ReportNotification(
            domain=self.DOMAIN,
            config_ids=[],
            hour=8,
            minute=0,
            stop_hour=16,
            stop_minute=0,
            send_to_owner=True,
            recipient_emails=[],
            language=None,
            interval="hourly",
        )
        soft_shift_to_server_timezone(report_notification)

        self.assertEqual(report_notification.hour, 18)
        self.assertEqual(report_notification.stop_hour, 2)

    def test_convert_to_domain_timezone(self):
        report_notification = ReportNotification(
            domain=self.DOMAIN,
            config_ids=[],
            hour=8,
            minute=0,
            stop_hour=16,
            stop_minute=0,
            send_to_owner=True,
            recipient_emails=[],
            language=None,
            interval="hourly",
        )
        soft_shift_to_domain_timezone(report_notification)

        self.assertEqual(report_notification.hour, 22)
        self.assertEqual(report_notification.stop_hour, 6)
