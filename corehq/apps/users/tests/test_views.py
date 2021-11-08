import json

from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CouchUser, WebUser, Permissions, CommCareUser, UserHistory
from corehq.apps.users.models import UserRole
from corehq.apps.users.views import _update_role_from_view
from corehq.apps.users.views.mobile.users import MobileWorkerListView
from corehq.const import USER_CHANGE_VIA_WEB
from corehq.util.test_utils import generate_cases


class TestMobileWorkerListView(TestCase):
    domain = 'mobile-worker-list-view'
    web_username = 'test-webuser'
    password = '***'

    def setUp(self):
        super().setUp()
        self.project = create_domain(self.domain)
        self.web_user = WebUser.create(self.domain, self.web_username, self.password, None, None)

        # We aren't testing permissions for this test
        self.web_user.is_superuser = True
        self.web_user.save()

    def tearDown(self):
        self.project.delete()
        delete_all_users()
        super().tearDown()

    def _remote_invoke(self, route, data):
        self.client.login(username=self.web_username, password=self.password)
        return self.client.post(
            reverse(MobileWorkerListView.urlname, args=[self.domain]),
            json.dumps(data),
            content_type='application/json;charset=UTF-8',
            HTTP_DJNG_REMOTE_METHOD=route,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_create_mobile_worker(self):
        resp = self._remote_invoke('create_mobile_worker', {
            "user": {
                "first_name": "Test",
                "last_name": "Test",
                "username": "test.test",
                "password": "123"
            }
        })
        content = json.loads(resp.content)
        self.assertEqual(content['success'], True)
        user = CouchUser.get_by_username(
            '{}@{}.commcarehq.org'.format(
                'test.test',
                self.domain,
            )
        )


@generate_cases((
    ('jmoney', False),
    ('jmoney91', False),
    ('j+money', False),
    ('j.money', False),
    ('j_money', False),
    ('j-money', False),
    ('j$', True),
    ('jmoney@something', True),
    ('jmoney...', True),
    ('.jmoney', True),
), TestMobileWorkerListView)
def test_check_usernames_for_invalid_characters(self, username, error):
    resp = self._remote_invoke('check_username', {
        'username': username
    })
    content = json.loads(resp.content)
    self.assertIs('error' in content, error)


class TestUpdateRoleFromView(TestCase):
    domain = "test_update_role"

    BASE_JSON = {
        'domain': domain,
        'name': None,
        'default_landing_page': 'webapps',
        'is_non_admin_editable': False,
        'is_archived': False,
        'upstream_id': None,
        'permissions': Permissions(edit_web_users=True).to_json(),
        'assignable_by': []
    }

    @classmethod
    def setUpTestData(cls):
        cls.role = UserRole(
            domain=cls.domain,
            name="role1",
        )
        cls.role.save()

    @classmethod
    def tearDownClass(cls):
        cls.role.delete()
        super().tearDownClass()

    def tearDown(self):
        for role in UserRole.objects.all():
            if role.id != self.role.id:
                role.delete()

    def test_create_role(self):
        role_data = self.BASE_JSON.copy()
        role_data["name"] = "role2"
        role_data["assignable_by"] = [self.role.couch_id]
        role = _update_role_from_view(self.domain, role_data)
        self.assertEqual(role.name, "role2")
        self.assertEqual(role.default_landing_page, "webapps")
        self.assertFalse(role.is_non_admin_editable)
        self.assertEqual(role.assignable_by, [self.role.couch_id])
        self.assertEqual(role.permissions.to_json(), role_data['permissions'])
        return role

    def test_create_role_duplicate_name(self):
        role_data = self.BASE_JSON.copy()
        role_data["name"] = "role1"
        with self.assertRaises(ValueError):
            _update_role_from_view(self.domain, role_data)

    def test_update_role(self):
        role = self.test_create_role()

        role_data = self.BASE_JSON.copy()
        role_data["_id"] = role.get_id
        role_data["name"] = "role1"  # duplicate name during update is OK for now
        role_data["default_landing_page"] = None
        role_data["is_non_admin_editable"] = True
        role_data["permissions"] = Permissions(edit_reports=True, view_report_list=["report1"]).to_json()
        updated_role = _update_role_from_view(self.domain, role_data)
        self.assertEqual(updated_role.name, "role1")
        self.assertIsNone(updated_role.default_landing_page)
        self.assertTrue(updated_role.is_non_admin_editable)
        self.assertEqual(updated_role.assignable_by, [])
        self.assertEqual(updated_role.permissions.to_json(), role_data['permissions'])

    def test_landing_page_validation(self):
        role_data = self.BASE_JSON.copy()
        role_data["default_landing_page"] = "bad value"
        with self.assertRaises(ValueError):
            _update_role_from_view(self.domain, role_data)


class TestDeletePhoneNumberView(TestCase):
    domain = 'test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.webuser_username = f"webuser@{cls.domain}.commcarehq.org"
        cls.dummy_password = "******"
        cls.project = create_domain(cls.domain)
        cls.web_user = WebUser.create(cls.domain, cls.webuser_username, cls.dummy_password,
                                      None, None)
        cls.web_user.set_role(cls.domain, 'admin')
        cls.web_user.save()
        cls.commcare_user = CommCareUser.create(cls.domain, "test-user", cls.dummy_password, None, None)

    @classmethod
    def tearDownClass(cls):
        cls.commcare_user.delete(cls.domain, deleted_by=None)
        cls.web_user.delete(cls.domain, deleted_by=None)
        cls.project.delete()
        super().tearDownClass()

    def setUp(self):
        self.client.login(username=self.webuser_username, password=self.dummy_password)

    def test_no_phone_number(self):
        response = self.client.post(
            reverse('delete_phone_number', args=[self.domain, self.commcare_user.get_id]),
            {'phone_number': ''}
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_phone_number(self):
        phone_number = '99999999'
        self.client.post(
            reverse('delete_phone_number', args=[self.domain, self.commcare_user.get_id]),
            {'phone_number': phone_number}
        )

        user_history_log = UserHistory.objects.get(user_id=self.commcare_user.get_id)
        self.assertIsNone(user_history_log.message)
        self.assertEqual(user_history_log.change_messages,
                         UserChangeMessage.phone_numbers_updated(removed=[phone_number]))
        self.assertEqual(user_history_log.changed_by, self.web_user.get_id)
        self.assertEqual(user_history_log.by_domain, self.domain)
        self.assertEqual(user_history_log.for_domain, self.domain)
        self.assertEqual(user_history_log.changed_via, USER_CHANGE_VIA_WEB)
