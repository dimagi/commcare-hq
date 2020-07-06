import json
from copy import deepcopy
from mock import patch

from django.urls import reverse
from django.utils.http import urlencode

from flaky import flaky

from corehq.apps.api.resources import v0_5
from corehq.apps.groups.models import Group
from corehq.apps.users.analytics import update_analytics_indexes
from corehq.apps.users.models import (
    CommCareUser,
    Permissions,
    UserRole,
    WebUser,
)
from corehq.elastic import send_to_elasticsearch
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.util.elastic import reset_es_index
from corehq.util.es.testing import sync_users_to_es

from .utils import APIResourceTest


class TestCommCareUserResource(APIResourceTest):
    """
    Basic sanity checking of v0_1.CommCareUserResource
    """
    resource = v0_5.CommCareUserResource
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        reset_es_index(USER_INDEX_INFO)
        super().setUpClass()

    @sync_users_to_es()
    def test_get_list(self):

        commcare_user = CommCareUser.create(domain=self.domain.name, username='fake_user', password='*****',
                                            created_by=None, created_via=None)
        self.addCleanup(commcare_user.delete)
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
            'first_name': '',
            'groups': [],
            'id': backend_id,
            'last_name': '',
            'phone_numbers': [],
            'resource_uri': '/a/qwerty/api/v0.5/user/{}/'.format(backend_id),
            'user_data': {'commcare_project': 'qwerty'},
            'username': 'fake_user'
        })

    @flaky
    def test_get_single(self):

        commcare_user = CommCareUser.create(domain=self.domain.name, username='fake_user', password='*****',
                                            created_by=None, created_via=None)
        self.addCleanup(commcare_user.delete)
        backend_id = commcare_user._id

        response = self._assert_auth_get_resource(self.single_endpoint(backend_id))
        self.assertEqual(response.status_code, 200)

        api_user = json.loads(response.content)
        self.assertEqual(api_user['id'], backend_id)
        self.assertEqual(api_user, {
            'default_phone_number': None,
            'email': '',
            'first_name': '',
            'groups': [],
            'id': backend_id,
            'last_name': '',
            'phone_numbers': [],
            'resource_uri': '/a/qwerty/api/v0.5/user/{}/'.format(backend_id),
            'user_data': {'commcare_project': 'qwerty'},
            'username': 'fake_user',
        })

    def test_create(self):

        group = Group({"name": "test"})
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
        self.addCleanup(user_back.delete)
        self.addCleanup(lambda: send_to_elasticsearch('users', user_back.to_json(), delete=True))

        self.assertEqual(user_back.username, "jdoe")
        self.assertEqual(user_back.first_name, "John")
        self.assertEqual(user_back.last_name, "Doe")
        self.assertEqual(user_back.email, "jdoe@example.org")
        self.assertEqual(user_back.language, "en")
        self.assertEqual(user_back.get_group_ids()[0], group._id)
        self.assertEqual(user_back.user_data["chw_id"], "13/43/DFA")
        self.assertEqual(user_back.default_phone_number, "50253311399")

    def test_update(self):

        user = CommCareUser.create(domain=self.domain.name, username="test", password="qwer1234",
                                   created_by=None, created_via=None)
        group = Group({"name": "test"})
        group.save()

        self.addCleanup(user.delete)
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
                "chw_id": "13/43/DFA"
            }
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
        self.assertEqual(modified.user_data["chw_id"], "13/43/DFA")
        self.assertEqual(modified.default_phone_number, "50253311399")


class TestWebUserResource(APIResourceTest):
    """
    Basic sanity checking of v0_1.CommCareUserResource
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
            "view_reports": True
        },
        "phone_numbers": [
        ],
        "role": "Admin"
    }

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
        another_user.set_role(self.domain.name, 'field-implementer')
        another_user.save()
        self.addCleanup(another_user.delete)

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        api_users = json.loads(response.content)['objects']
        self.assertEqual(len(api_users), 2)

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

    def test_create(self):
        user_json = deepcopy(self.default_user_json)
        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json')
        self.assertEqual(response.status_code, 201)
        user_back = WebUser.get_by_username("test_1234")
        self.assertEqual(user_back.username, "test_1234")
        self.assertEqual(user_back.first_name, "Joe")
        self.assertEqual(user_back.last_name, "Admin")
        self.assertEqual(user_back.email, "admin@example.com")
        self.assertTrue(user_back.is_domain_admin(self.domain.name))
        user_back.delete()

    def test_create_admin_without_role(self):
        user_json = deepcopy(self.default_user_json)
        user_json.pop('role')
        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json')
        self.assertEqual(response.status_code, 201)
        user_back = WebUser.get_by_username("test_1234")
        self.assertEqual(user_back.username, "test_1234")
        self.assertEqual(user_back.first_name, "Joe")
        self.assertEqual(user_back.last_name, "Admin")
        self.assertEqual(user_back.email, "admin@example.com")
        self.assertTrue(user_back.is_domain_admin(self.domain.name))
        user_back.delete()

    def test_create_with_preset_role(self):
        user_json = deepcopy(self.default_user_json)
        user_json["role"] = "Field Implementer"
        user_json["is_admin"] = False
        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json')
        self.assertEqual(response.status_code, 201)
        user_back = WebUser.get_by_username("test_1234")
        self.assertEqual(user_back.role, 'Field Implementer')
        user_back.delete()

    def test_create_with_custom_role(self):
        new_user_role = UserRole.get_or_create_with_permissions(
            self.domain.name, Permissions(edit_apps=True, view_reports=True), 'awesomeness')
        user_json = deepcopy(self.default_user_json)
        user_json["role"] = new_user_role.name
        user_json["is_admin"] = False
        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json')
        self.assertEqual(response.status_code, 201)
        user_back = WebUser.get_by_username("test_1234")
        self.assertEqual(user_back.role, new_user_role.name)
        user_back.delete()

    def test_create_with_invalid_admin_role(self):
        user_json = deepcopy(self.default_user_json)
        user_json["role"] = 'Jack of all trades'
        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json',
                                                   failure_code=400)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode('utf-8'), '{"error": "An admin can have only one role : Admin"}')

    def test_create_with_invalid_non_admin_role(self):
        user_json = deepcopy(self.default_user_json)
        user_json['is_admin'] = False
        user_json["role"] = 'Jack of all trades'
        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json',
                                                   failure_code=400)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode('utf-8'), '{"error": "Invalid User Role Jack of all trades"}')

    def test_create_with_missing_non_admin_role(self):
        user_json = deepcopy(self.default_user_json)
        user_json['is_admin'] = False
        user_json.pop("role")
        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json',
                                                   failure_code=400)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode('utf-8'), '{"error": "Please assign role for non admin user"}')

    def test_update(self):
        user = WebUser.create(domain=self.domain.name, username="test", password="qwer1234",
                              created_by=None, created_via=None)
        self.addCleanup(user.delete)
        user_json = deepcopy(self.default_user_json)
        user_json.pop('username')
        backend_id = user._id
        response = self._assert_auth_post_resource(self.single_endpoint(backend_id),
                                                   json.dumps(user_json),
                                                   content_type='application/json',
                                                   method='PUT')
        self.assertEqual(response.status_code, 200, response.content)
        modified = WebUser.get(backend_id)
        self.assertEqual(modified.username, "test")
        self.assertEqual(modified.first_name, "Joe")
        self.assertEqual(modified.last_name, "Admin")
        self.assertEqual(modified.email, "admin@example.com")


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
