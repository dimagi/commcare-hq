import os

from django.contrib.messages import get_messages
from django.http import HttpResponse
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from lxml import etree
from unittest.mock import Mock, patch

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.hqadmin.views.users import AdminRestoreView, DisableUserView
from corehq.apps.users.models import WebUser
from corehq.toggles import TAG_CUSTOM, TAG_SOLUTIONS
from corehq.toggles.sql_models import ToggleEditPermission


class AdminRestoreViewTests(TestXmlMixin, SimpleTestCase):
    root = os.path.dirname(__file__)
    file_path = ['data']
    maxDiff = None

    def test_bad_restore(self):
        user = Mock()
        domain = None
        app_id = None
        request = Mock()
        request.GET = {}
        request.openrosa_headers = {}
        timing_context = Mock()
        timing_context.to_list.return_value = []
        with patch('corehq.apps.hqadmin.views.users.get_restore_response',
                   return_value=(HttpResponse('bad response', status=500), timing_context)):

            view = AdminRestoreView(user=user, app_id=app_id, request=request, domain=domain)
            context = view.get_context_data(foo='bar', view='AdminRestoreView')
            self.assertEqual(context, {
                'foo': 'bar',
                'view': 'AdminRestoreView',
                'payload': '<error>Unexpected restore response 500: bad response. If you believe this is a bug '
                           'please report an issue.</error>\n',
                'status_code': 500,
                'timing_data': [],
                'hide_xml': False,
            })

    def test_admin_restore_counts(self):
        xml_payload = etree.fromstring(self.get_xml('restore'))
        self.assertEqual(AdminRestoreView.get_stats_from_xml(xml_payload), {
            'restore_id': '02bbfb3ea17711e8adb9bc764e203eaf',
            'num_cases': 2,
            'num_locations': 7,
            'num_v1_reports': 2,
            'num_v2_reports': 2,
            'case_type_counts': {},
            'location_type_counts': {
                'country': 1,
                'state': 1,
                'county': 1,
                'city': 1,
                'neighborhood': 3,
            },
            'v1_report_row_counts': {
                'e009c3dc89b0250a8accd09b9641c3250f4e38d0--0dc41ff3e342d3ac94c06bb5c6cdd416': 3,
                '42dc83c562a474b7e5faba4fc3190ca37bd4777f--f1761733213601f7f77defc3bc2e2c87': 3,
            },
            'v2_report_row_counts': {
                'commcare-reports:e009c3dc89b0250a8accd09b9641c3250f4e38d0--0dc41ff3e342d3ac94c06bb5c6cdd416': 3,
                'commcare-reports:42dc83c562a474b7e5faba4fc3190ca37bd4777f--f1761733213601f7f77defc3bc2e2c87': 3,
            },
            'num_ledger_entries': 0,
        })


class DisableUserViewTests(SimpleTestCase):

    def test_redirect_url_username_is_encoded(self):
        user = Mock()
        request = Mock()
        request.GET = {
            'username': 'test+example@dimagi.com'
        }
        view = DisableUserView(user=user, request=request)
        with patch('corehq.apps.hqadmin.views.users.reverse') as mock_reverse:
            mock_reverse.return_value = 'dummy_url/'
            redirect_url = view.redirect_url

        self.assertEqual(redirect_url, 'dummy_url/?q=test%2Bexample%40dimagi.com')

    def test_redirect_url_returns_no_params_if_no_username(self):
        user = Mock()
        request = Mock()
        request.GET = {}
        view = DisableUserView(user=user, request=request)
        with patch('corehq.apps.hqadmin.views.users.reverse') as mock_reverse:
            mock_reverse.return_value = 'dummy_url'
            redirect_url = view.redirect_url

        self.assertEqual(redirect_url, 'dummy_url')


class TestSuperuserManagementView(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.superuser = WebUser.create(None, "superuser@dimagi.com", "password", None, None, is_superuser=True)
        cls.regular_user = WebUser.create(None, "regular@dimagi.com", "password", None, None)
        cls.superuser_with_permission_to_manage = WebUser.create(
            None, "support@dimagi.com", "password", None, None, is_superuser=True
        )
        cls.superuser_with_permission_to_manage.can_assign_superuser = True
        cls.superuser_with_permission_to_manage.save()
        cls.url = reverse('superuser_management')

    @classmethod
    def tearDownClass(cls):
        cls.superuser.delete(None, None)
        cls.regular_user.delete(None, None)
        cls.superuser_with_permission_to_manage.delete(None, None)
        super().tearDownClass()

    def test_superuser_access(self):
        self.client.login(username=self.superuser.username, password='password')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_non_superuser_cannot_access(self):
        self.client.login(username=self.regular_user.username, password='password')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_permission_to_manage_privileges(self):
        self.client.login(username=self.superuser.username, password='password')
        response = self.client.post(self.url, data={})

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "You do not have permission to update superuser or staff status")

    def test_update_user_privileges(self):
        user = WebUser.create(None, "test-user@dimagi.com", "password", None, None)
        self.addCleanup(user.delete, None, None)
        data = {
            'csv_email_list': user.username,
            'privileges': ['is_superuser', 'is_staff'],
            'feature_flag_edit_permissions': [TAG_SOLUTIONS.slug, TAG_CUSTOM.slug],
            'can_assign_superuser': ['can_assign_superuser']
        }

        self.client.login(username=self.superuser_with_permission_to_manage.username, password='password')
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        updated_user = WebUser.get_by_username(user.username)
        self.assertTrue(updated_user.is_superuser)
        self.assertTrue(updated_user.is_staff)
        self.assertTrue(updated_user.can_assign_superuser)
        for tag_slug in [TAG_SOLUTIONS.slug, TAG_CUSTOM.slug]:
            permission = ToggleEditPermission.get_by_tag_slug(tag_slug)
            self.assertIn(user.username, permission.enabled_users)
