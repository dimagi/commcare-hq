import json
from unittest.mock import Mock, patch

from django.test import TestCase
from django.urls import reverse
from django.utils.http import urlencode

from flaky import flaky
from tastypie.bundle import Bundle

from corehq.apps.api.resources import v0_5
from corehq.apps.custom_data_fields.models import (
    PROFILE_SLUG,
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.groups.models import Group
from corehq.apps.users.analytics import update_analytics_indexes
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.model_log import UserModelAction
from corehq.apps.users.models import (
    CommCareUser,
    ConnectIDUserLink,
    UserHistory,
    UserRole,
    WebUser,
)
from corehq.apps.users.role_utils import (
    UserRolePresets,
    initialize_domain_with_default_roles,
)
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.const import USER_CHANGE_VIA_API
from corehq.util.es.testing import sync_users_to_es
from corehq.util.test_utils import flag_enabled

from ..resources.v0_5 import BadRequest, UserDomainsResource
from .utils import APIResourceTest


@es_test(requires=[user_adapter], setup_class=True)
class TestCommCareUserResource(APIResourceTest):
    """
    Basic sanity checking of v0_5.CommCareUserResource
    """
    resource = v0_5.CommCareUserResource
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.definition = CustomDataFieldsDefinition(domain=cls.domain.name,
                                                    field_type=UserFieldsView.field_type)
        cls.definition.save()
        cls.definition.set_fields([
            Field(
                slug='imaginary',
                label='Imaginary Person',
                choices=['yes', 'no'],
            ),
        ])
        cls.definition.save()
        cls.profile = CustomDataFieldsProfile(
            name='character',
            fields={'imaginary': 'yes'},
            definition=cls.definition,
        )
        cls.profile.save()

    @classmethod
    def tearDownClass(cls):
        cls.definition.delete()
        super().tearDownClass()

    @sync_users_to_es()
    def test_get_list(self):
        commcare_user = CommCareUser.create(domain=self.domain.name, username='fake_user', password='*****',
                                            created_by=None, created_via=None)
        self.addCleanup(commcare_user.delete, self.domain.name, deleted_by=None)
        backend_id = commcare_user.get_id
        update_analytics_indexes()

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_users = json.loads(response.content)['objects']
        self.assertEqual(len(api_users), 1, api_users)
        self.assertEqual(api_users[0]['id'], backend_id)
        self.assertEqual(api_users[0], {
            'default_phone_number': None,
            'email': '',
            'eulas': '[]',
            'first_name': '',
            'groups': [],
            'id': backend_id,
            'last_name': '',
            'phone_numbers': [],
            'resource_uri': '/a/qwerty/api/v0.5/user/{}/'.format(backend_id),
            'user_data': {'commcare_project': 'qwerty', PROFILE_SLUG: '', 'imaginary': ''},
            'username': 'fake_user'
        })

    @flaky
    def test_get_single(self):
        commcare_user = CommCareUser.create(domain=self.domain.name, username='fake_user', password='*****',
                                            created_by=None, created_via=None)
        self.addCleanup(commcare_user.delete, self.domain.name, deleted_by=None)
        backend_id = commcare_user._id

        response = self._assert_auth_get_resource(self.single_endpoint(backend_id))
        self.assertEqual(response.status_code, 200)

        api_user = json.loads(response.content)
        self.assertEqual(api_user['id'], backend_id)
        self.assertEqual(api_user, {
            'default_phone_number': None,
            'email': '',
            'eulas': '[]',
            'first_name': '',
            'groups': [],
            'id': backend_id,
            'last_name': '',
            'phone_numbers': [],
            'resource_uri': '/a/qwerty/api/v0.5/user/{}/'.format(backend_id),
            'user_data': {'commcare_project': 'qwerty', PROFILE_SLUG: '', 'imaginary': ''},
            'username': 'fake_user',
        })

    def test_create(self):
        group = Group({"name": "test", "domain": self.domain.name})
        group.save()
        self.addCleanup(group.delete)

        self.assertEqual(0, len(CommCareUser.by_domain(self.domain.name)))

        user_json = {
            "username": "jdoe",
            "password": "qwer1234",
            "first_name": "John",
            "last_name": "Doe",
            "email": "jdoe@example.org",
            "language": "en",
            "phone_numbers": [
                "+50253311399",
                "50253314588"
            ],
            "groups": [
                group._id
            ],
            "user_data": {
                "chw_id": "13/43/DFA"
            }
        }
        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json')
        self.assertEqual(response.status_code, 201)
        [user_back] = CommCareUser.by_domain(self.domain.name)
        self.addCleanup(user_back.delete, self.domain.name, deleted_by=None)

        # tests username is normalized before saving
        self.assertEqual(user_back.username, "jdoe@qwerty.commcarehq.org")
        self.assertEqual(user_back.first_name, "John")
        self.assertEqual(user_back.last_name, "Doe")
        self.assertEqual(user_back.email, "jdoe@example.org")
        self.assertEqual(user_back.language, "en")
        self.assertEqual(user_back.get_group_ids()[0], group._id)
        self.assertEqual(user_back.get_user_data(self.domain.name)["chw_id"], "13/43/DFA")
        self.assertEqual(user_back.default_phone_number, "50253311399")

    @flag_enabled('COMMCARE_CONNECT')
    def test_create_connect_user_no_password(self):
        user_json = {
            "username": "ccc",
            "connect_username": "ccc_user",
        }

        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json')
        self.assertEqual(response.status_code, 201)
        user = CommCareUser.get_by_username("ccc@qwerty.commcarehq.org")
        self.addCleanup(user.delete, self.domain.name, deleted_by=None)

        django_user = user.get_django_user()
        user_link = ConnectIDUserLink.objects.get(commcare_user=django_user)
        self.addCleanup(user_link.delete)
        self.assertEqual(user_link.domain, self.domain.name)
        self.assertEqual(user_link.connectid_username, "ccc_user")

    @flag_enabled('COMMCARE_CONNECT')
    def test_create_connect_user_with_password(self):
        user_json = {
            "username": "ccc",
            "connect_username": "ccc_user",
            "password": "abc123",
        }

        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json')
        self.assertEqual(response.status_code, 201)
        user = CommCareUser.get_by_username("ccc@qwerty.commcarehq.org")
        self.addCleanup(user.delete, self.domain.name, deleted_by=None)

        django_user = user.get_django_user()
        user_link = ConnectIDUserLink.objects.get(commcare_user=django_user)
        self.addCleanup(user_link.delete)
        self.assertEqual(user_link.domain, self.domain.name)
        self.assertEqual(user_link.connectid_username, "ccc_user")

    def test_create_connect_user_no_flag(self):
        user_json = {
            "username": "ccc",
            "connect_username": "ccc_user",
        }

        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_bad_request_if_username_already_exists(self):
        # create user with same username first
        og_user = CommCareUser.create(self.domain.name, 'jdoe@qwerty.commcarehq.org', 'abc123', None, None)
        self.addCleanup(og_user.delete, self.domain.name, deleted_by=None)

        user_json = {
            "username": "jdoe",
            "password": "qwer1234",
        }
        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode('utf-8'),
                         f'{{"error": "Username \'jdoe@{self.domain.name}.commcarehq.org\' is already taken or '
                         f'reserved."}}')

    def test_update(self):
        user = CommCareUser.create(domain=self.domain.name, username="test", password="qwer1234",
                                   created_by=None, created_via=None, phone_number="50253311398")
        group = Group({"name": "test", "domain": self.domain.name})
        group.save()

        self.addCleanup(user.delete, self.domain.name, deleted_by=None)
        self.addCleanup(group.delete)

        user_json = {
            "first_name": "test",
            "last_name": "last",
            "email": "tlast@example.org",
            "language": "pol",
            "phone_numbers": [
                "+50253311399",
                "50253314588"
            ],
            "groups": [
                group._id
            ],
            "user_data": {
                PROFILE_SLUG: self.profile.id,
                "chw_id": "13/43/DFA"
            },
            "password": "qwerty1234"
        }

        backend_id = user._id
        response = self._assert_auth_post_resource(self.single_endpoint(backend_id),
                                                   json.dumps(user_json),
                                                   content_type='application/json',
                                                   method='PUT')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(1, len(CommCareUser.by_domain(self.domain.name)))
        modified = CommCareUser.get(backend_id)
        self.assertEqual(modified.username, "test")
        self.assertEqual(modified.first_name, "test")
        self.assertEqual(modified.last_name, "last")
        self.assertEqual(modified.email, "tlast@example.org")
        self.assertEqual(modified.language, "pol")
        self.assertEqual(modified.get_group_ids()[0], group._id)
        user_data = modified.get_user_data(self.domain.name)
        self.assertEqual(user_data["chw_id"], "13/43/DFA")
        self.assertEqual(user_data.profile_id, self.profile.id)
        self.assertEqual(user_data["imaginary"], "yes")
        self.assertEqual(modified.default_phone_number, "50253311399")

        # test user history audit
        user_history = UserHistory.objects.get(action=UserModelAction.UPDATE.value,
                                               user_id=user._id)
        self.assertDictEqual(
            user_history.changes,
            {
                'email': 'tlast@example.org',
                'language': 'pol',
                'last_name': 'last',
                'first_name': 'test',
                'user_data': {'chw_id': '13/43/DFA'},
            }
        )
        self.assertTrue("50253311398" in
                        user_history.change_messages['phone_numbers']['remove_phone_numbers']['phone_numbers'])
        self.assertTrue("50253311399" in
                        user_history.change_messages['phone_numbers']['add_phone_numbers']['phone_numbers'])
        self.assertTrue("50253314588" in
                        user_history.change_messages['phone_numbers']['add_phone_numbers']['phone_numbers'])
        self.assertEqual(
            user_history.change_messages['groups'],
            UserChangeMessage.groups_info([group])['groups']
        )
        self.assertEqual(user_history.change_messages['password'], UserChangeMessage.password_reset()['password'])
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_API)

    def test_update_fails(self):
        user = CommCareUser.create(domain=self.domain.name, username="test", password="qwer1234",
                                   created_by=None, created_via=None, phone_number="50253311398")
        group = Group({"name": "test"})
        group.save()

        self.addCleanup(user.delete, self.domain.name, deleted_by=None)
        self.addCleanup(group.delete)

        user_json = {
            "username": "updated-username",
            "default_phone_number": 1234567890
        }

        backend_id = user._id
        response = self._assert_auth_post_resource(self.single_endpoint(backend_id),
                                                   json.dumps(user_json),
                                                   content_type='application/json',
                                                   method='PUT')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.content.decode('utf-8'),
            "{\"error\": \"The request resulted in the following errors: Attempted to update unknown or "
            "non-editable field 'username', 'default_phone_number' must be a string\"}"
        )


class TestWebUserResource(APIResourceTest):
    """
    Basic sanity checking of v0_5.WebUserResource
    """
    resource = v0_5.WebUserResource
    api_name = 'v0.5'
    default_user_json = {
        "username": "test_1234",
        "password": "qwer1234",
        "email": "admin@example.com",
        "first_name": "Joe",
        "is_admin": True,
        "last_name": "Admin",
        "permissions": {
            "edit_apps": True,
            "view_apps": True,
            "edit_commcare_users": True,
            "view_commcare_users": True,
            "edit_groups": True,
            "view_groups": True,
            "edit_users_in_groups": True,
            "edit_locations": True,
            "view_locations": True,
            "edit_users_in_locations": True,
            "edit_data": True,
            "edit_web_users": True,
            "view_web_users": True,
            "view_roles": True,
            "edit_reports": True,
            "view_reports": True,
        },
        "phone_numbers": [
        ],
        "role": "Admin"
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        initialize_domain_with_default_roles(cls.domain.name)

    def _check_user_data(self, user, json_user):
        self.assertEqual(user._id, json_user['id'])
        role = user.get_role(self.domain.name)
        self.assertEqual(role.name, json_user['role'])
        self.assertEqual(user.is_domain_admin(self.domain.name), json_user['is_admin'])
        for perm in [
            'edit_web_users',
            'view_web_users',
            'view_roles',
            'edit_commcare_users',
            'view_commcare_users',
            'edit_groups',
            'view_groups',
            'edit_users_in_groups',
            'edit_locations',
            'view_locations',
            'edit_users_in_locations',
            'edit_data',
            'edit_apps',
            'view_apps',
            'edit_reports',
            'view_reports',
        ]:
            self.assertEqual(getattr(role.permissions, perm), json_user['permissions'][perm])

    def test_get_list(self):

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_users = json.loads(response.content)['objects']
        self.assertEqual(len(api_users), 1)
        self._check_user_data(self.user, api_users[0])

        another_user = WebUser.create(self.domain.name, 'anotherguy', '***', None, None)
        role = UserRole.objects.get(domain=self.domain, name=UserRolePresets.FIELD_IMPLEMENTER)
        another_user.set_role(self.domain.name, role.get_qualified_id())
        another_user.save()
        self.addCleanup(another_user.delete, self.domain.name, deleted_by=None)

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        api_users = json.loads(response.content)['objects']
        self.assertEqual(len(api_users), 2)

        response = self._assert_auth_get_resource('%s?limit=1' % (self.list_endpoint))
        self.assertEqual(response.status_code, 200)
        response_json = json.loads(response.content)
        self.assertEqual(len(response_json['objects']), 1)
        self.assertEqual(response_json['meta']['next'], "?limit=1&offset=1")

        # username filter
        response = self._assert_auth_get_resource('%s?web_username=%s' % (self.list_endpoint, 'anotherguy'))
        self.assertEqual(response.status_code, 200)
        api_users = json.loads(response.content)['objects']
        self.assertEqual(len(api_users), 1)
        self._check_user_data(another_user, api_users[0])

        response = self._assert_auth_get_resource('%s?web_username=%s' % (self.list_endpoint, 'nomatch'))
        self.assertEqual(response.status_code, 200)
        api_users = json.loads(response.content)['objects']
        self.assertEqual(len(api_users), 0)

    def test_get_single(self):

        response = self._assert_auth_get_resource(self.single_endpoint(self.user._id))
        self.assertEqual(response.status_code, 200)

        api_user = json.loads(response.content)
        self._check_user_data(self.user, api_user)

    def _delete_user(self, username):
        user = WebUser.get_by_username(username)
        if user:
            user.delete(self.domain.name, deleted_by=None)


class FakeUserES(object):

    def __init__(self):
        self.docs = []
        self.queries = []

    def add_doc(self, doc):
        self.docs.append(doc)

    def make_query(self, q=None, fields=None, domain=None, start_at=None, size=None):
        self.queries.append(q)
        start = int(start_at) if start_at else 0
        end = min(len(self.docs), start + int(size)) if size else None
        return self.docs[start:end]


class TestBulkUserAPI(APIResourceTest):
    resource = v0_5.BulkUserResource
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super(TestBulkUserAPI, cls).setUpClass()
        cls.fake_user_es = FakeUserES()
        v0_5.MOCK_BULK_USER_ES = cls.mock_es_wrapper
        cls.make_users()

    @classmethod
    def tearDownClass(cls):
        v0_5.MOCK_BULK_USER_ES = None
        super(TestBulkUserAPI, cls).tearDownClass()

    @classmethod
    def make_users(cls):
        users = [
            ('Robb', 'Stark'),
            ('Jon', 'Snow'),
            ('Brandon', 'Stark'),
            ('Eddard', 'Stark'),
            ('Catelyn', 'Stark'),
            ('Tyrion', 'Lannister'),
            ('Tywin', 'Lannister'),
            ('Jamie', 'Lannister'),
            ('Cersei', 'Lannister'),
        ]
        for first, last in users:
            username = '_'.join([first.lower(), last.lower()])
            email = username + '@qwerty.commcarehq.org'
            cls.fake_user_es.add_doc({
                'id': 'lskdjflskjflaj',
                'email': email,
                'username': username,
                'first_name': first,
                'last_name': last,
                'phone_numbers': ['9042411080'],
            })

    @classmethod
    def mock_es_wrapper(cls, *args, **kwargs):
        return cls.fake_user_es.make_query(**kwargs)

    @property
    def list_endpoint(self):
        return reverse(
            'api_dispatch_list',
            kwargs={
                'domain': self.domain.name,
                'api_name': self.api_name,
                'resource_name': self.resource.Meta.resource_name,
            }
        )

    def test_excluded_field(self):
        result = self.query(fields=['email', 'first_name', 'password'])
        self.assertEqual(result.status_code, 400)

    def query(self, **params):
        url = '%s?%s' % (self.list_endpoint, urlencode(params, doseq=True))
        return self._assert_auth_get_resource(url)

    def test_paginate(self):
        limit = 3
        result = self.query(limit=limit)
        self.assertEqual(result.status_code, 200)
        users = json.loads(result.content)['objects']
        self.assertEqual(len(users), limit)

        result = self.query(start_at=limit, limit=limit)
        self.assertEqual(result.status_code, 200)
        users = json.loads(result.content)['objects']
        self.assertEqual(len(users), limit)

    def test_basic(self):
        response = self.query()
        self.assertEqual(response.status_code, 200)


@es_test(requires=[user_adapter])
class TestIdentityResource(APIResourceTest):
    resource = v0_5.IdentityResource
    api_name = 'v0.5'

    @classmethod
    def _get_list_endpoint(cls):
        return reverse('api_dispatch_list',
                       kwargs=dict(api_name=cls.api_name,
                                   resource_name=cls.resource._meta.resource_name))

    @sync_users_to_es()
    def test_get_list(self):
        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['id'], self.user.get_id)
        self.assertEqual(data['username'], self.username)
        self.assertEqual(data['first_name'], self.user.first_name)
        self.assertEqual(data['last_name'], self.user.last_name)
        self.assertEqual(data['email'], self.user.email)


class TestUserDomainsResource(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.definition = CustomDataFieldsDefinition(domain=cls.domain,
                                                    field_type=UserFieldsView.field_type)
        cls.definition.save()

    def setUp(self) -> None:
        super().setUp()
        self.user = CommCareUser.create(self.domain, "test-username", "qwer1234", None, None)
        self.addCleanup(self.user.delete, self.domain, deleted_by=None)

    @patch('corehq.apps.api.resources.v0_5.domain_has_privilege', return_value=True)
    def test_domain_returned_when_no_filter(self, _):
        bundle = Bundle()
        bundle.obj = self.user
        bundle.request = Mock()
        bundle.request.GET = {}
        bundle.request.user = self.user
        resp = UserDomainsResource().obj_get_list(bundle)
        self.assertListEqual([self.domain], [d.domain_name for d in resp])

    @patch('corehq.apps.api.resources.v0_5.domain_has_privilege', return_value=True)
    def test_exception_when_invalid_filter_sent(self, _):
        bundle = Bundle()
        bundle.obj = self.user
        bundle.request = Mock()
        bundle.request.GET = {"feature_flag": "its_a_feature_not_bug"}
        bundle.request.user = self.user
        with self.assertRaises(BadRequest):
            UserDomainsResource().obj_get_list(bundle)

    @patch('corehq.apps.api.resources.v0_5.domain_has_privilege', return_value=True)
    @patch('corehq.apps.api.resources.v0_5.toggles.toggles_dict', return_value={"superset-analytics": True})
    def test_domain_returned_when_valid_flag_sent(self, *args):
        bundle = Bundle()
        bundle.obj = self.user
        bundle.request = Mock()
        bundle.request.GET = {"feature_flag": "superset-analytics"}
        bundle.request.user = self.user
        resp = UserDomainsResource().obj_get_list(bundle)
        self.assertListEqual([self.domain], [d.domain_name for d in resp])

    @patch('corehq.apps.api.resources.v0_5.domain_has_privilege', return_value=True)
    def test_domain_not_returned_when_flag_not_enabled(self, *args):
        bundle = Bundle()
        bundle.obj = self.user
        bundle.request = Mock()
        bundle.request.GET = {"feature_flag": "superset-analytics"}
        bundle.request.user = self.user
        resp = UserDomainsResource().obj_get_list(bundle)
        self.assertEqual(0, len(resp))
