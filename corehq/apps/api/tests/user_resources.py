
import json
import uuid
from copy import deepcopy
from unittest import mock

from django.http import QueryDict
from django.test import RequestFactory
from django.urls import reverse
from django.utils.http import urlencode

from flaky import flaky
from tastypie.exceptions import NotFound, ImmediateHttpResponse, BadRequest

from corehq.apps.api.resources import v0_5
from corehq.apps.api.resources.v0_5 import UserDomain, CaseType, UserInfo
from corehq.apps.app_manager.models import Application, FormBase, ModuleBase
from corehq.apps.groups.models import Group
from corehq.apps.reports.analytics import esaccessors
from corehq.apps.users.analytics import update_analytics_indexes
from corehq.apps.users.models import (
    CommCareUser,
    Permissions,
    UserRole,
    WebUser,
)
from corehq.elastic import send_to_elasticsearch, get_es_new
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import create_and_save_a_case

from .utils import APIResourceTest


class TestCommCareUserResource(APIResourceTest):
    """
    Basic sanity checking of v0_1.CommCareUserResource
    """
    resource = v0_5.CommCareUserResource
    api_name = 'v0.5'

    def test_get_list(self):

        commcare_user = CommCareUser.create(domain=self.domain.name, username='fake_user', password='*****')
        self.addCleanup(commcare_user.delete)
        backend_id = commcare_user.get_id
        update_analytics_indexes()

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_users = json.loads(response.content)['objects']
        self.assertEqual(len(api_users), 1)
        self.assertEqual(api_users[0]['id'], backend_id)

    @flaky
    def test_get_single(self):

        commcare_user = CommCareUser.create(domain=self.domain.name, username='fake_user', password='*****')
        self.addCleanup(commcare_user.delete)
        backend_id = commcare_user._id

        response = self._assert_auth_get_resource(self.single_endpoint(backend_id))
        self.assertEqual(response.status_code, 200)

        api_user = json.loads(response.content)
        self.assertEqual(api_user['id'], backend_id)

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
        self.assertEqual(user_back.username, "jdoe")
        self.assertEqual(user_back.first_name, "John")
        self.assertEqual(user_back.last_name, "Doe")
        self.assertEqual(user_back.email, "jdoe@example.org")
        self.assertEqual(user_back.language, "en")
        self.assertEqual(user_back.get_group_ids()[0], group._id)
        self.assertEqual(user_back.user_data["chw_id"], "13/43/DFA")
        self.assertEqual(user_back.default_phone_number, "50253311399")

    def test_update(self):

        user = CommCareUser.create(domain=self.domain.name, username="test", password="qwer1234")
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

        another_user = WebUser.create(self.domain.name, 'anotherguy', '***')
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
        user = WebUser.create(domain=self.domain.name, username="test", password="qwer1234")
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


class BundleMock(object):

    def __init__(self, **params):
        query = ''
        for querykey in params:
            query = query + '{}={}&'.format(
                    querykey,
                    '&{}='.format(querykey).join(params.get(querykey))
                    )
        q = QueryDict(query, mutable=True)
        request = RequestFactory().get(TestBulkUserAPI.list_endpoint)
        request.GET = q
        self.request = request


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
        self.assertEquals(len(users), limit)

        result = self.query(start_at=limit, limit=limit)
        self.assertEqual(result.status_code, 200)
        users = json.loads(result.content)['objects']
        self.assertEquals(len(users), limit)

    def test_basic(self):
        response = self.query()
        self.assertEqual(response.status_code, 200)

    def test_obj_get_list(self):
        x = v0_5.BulkUserResource()
        base_bundle = BundleMock(**{'fields': ['username', 'first_name'],
                                    'limit': '3'
                                    })
        actual = x.obj_get_list(bundle=base_bundle, domain=self.domain)
        print(actual)
        self.assertTrue(isinstance(actual, list))
        self.assertEqual(len(actual), 3)

    def test_obj_get_list_wrong_fields(self):
        x = v0_5.BulkUserResource()
        base_bundle = BundleMock(**{'fields': ['wrong_field', 'first_name']})
        with self.assertRaises(BadRequest):
            x.obj_get_list(bundle=base_bundle, domain=self.domain)


class TestDomainForms(APIResourceTest):
    resource = v0_5.DomainForms
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super(TestDomainForms, cls).setUpClass()
        cls.create_user()
        cls.create_app()

    @classmethod
    def tearDownClass(cls):
        super(TestDomainForms, cls).tearDownClass()
        cls.unprivileged.delete()
        cls.application.delete_app()


    @classmethod
    def create_user(cls):
        cls.username2 = 'notprivileged@qwerty.commcarehq.org'
        cls.password2 = '*****'
        cls.unprivileged = WebUser.get_by_username(cls.username2)
        if cls.unprivileged is not None:
            cls.unprivileged.delete()
        cls.unprivileged = WebUser.create(None, cls.username2, cls.password2)
        cls.unprivileged.save()

    @classmethod
    def create_app(cls):
        cls.app_name = 'Application'

        cls.application = Application.new_app(cls.domain.name, cls.app_name)
        cls.application.save()

    @classmethod
    def mock_form_objects(cls):
        form_data = [
            ('name1', 'xmlnsa1'),
            ('form', 'xmlnsa31'),
            ('form2', 'xmlnsa31'),
        ]
        forms = []
        for name, xml in form_data:
            forms.append(cls.mock_single_form(name, xml))

        form_objects = []
        module = cls.mock_module('mod1', iter(forms))
        for form in forms:
            form_objects.append({'form': form,
                                 'module': module})

        return form_objects

    @classmethod
    def mock_single_form(cls, name, xmlns):
        form = mock.MagicMock(FormBase)
        form.xmlns = xmlns
        form.version = None
        form.default_name = mock.MagicMock(return_value=name)

        return form

    @classmethod
    def mock_module(cls, name, module_forms):
        module = mock.Mock(ModuleBase)
        module.default_name = mock.MagicMock(return_value=name)
        module.get_forms = mock.MagicMock(return_value=module_forms)

        return module

    def test_obj_get_list_app_not_found_exception(self):
        api = v0_5.DomainForms()
        bundle = BundleMock(**{'user': self.user})
        with self.assertRaises(NotFound):
            api.obj_get_list(bundle)

    def test_obj_get_list_unprivileged_exception(self):
        api = v0_5.DomainForms()
        bundle = BundleMock(**{'application_id': ['Application']})
        bundle.request.user = self.unprivileged

        with self.assertRaises(ImmediateHttpResponse):
            api.obj_get_list(bundle, domain=self.domain.name)

    @mock.patch('corehq.apps.app_manager.models.Application.get')
    def test_obj_get_list_no_forms(self, app):
        api = v0_5.DomainForms()
        with mock.patch.object(Application, "get_forms", ) as mock_forms:
            mock_forms.return_value = self.mock_form_objects()
            self.application2 = Application.new_app(self.domain.name, 'mock_app')
            app.return_value = self.application2
            bundle = BundleMock(**{'application_id': [self.application.id]})
            bundle.request.user = self.user
            result = api.obj_get_list(bundle, domain=self.domain.name)
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 3)
            self.assertRegexpMatches(result[0].form_name, '.* > .* > *.')

            self.application2.delete_app()

    def test_obj_get_list_no_forms2(self):
        api = v0_5.DomainForms()
        bundle = BundleMock(**{'application_id': [self.application.id]})
        bundle.request.user = self.user
        result = api.obj_get_list(bundle, domain=self.domain.name)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)


class TestStockTransactionResource(APIResourceTest):
    resource = v0_5.StockTransactionResource
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super(TestStockTransactionResource, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(TestStockTransactionResource, cls).tearDownClass()

    def test_building_filters(self):
        date1 = 'start'
        date2 = 'end'
        api = v0_5.StockTransactionResource()
        filters = {'start_date': date1,
                   'end_date': date2}
        orm_filters = api.build_filters(filters=filters)
        self.assertEqual(orm_filters['report__date__gte'], date1)
        self.assertEqual(orm_filters['report__date__lte'], date2)

    def test_dehydrate(self):
        bm = self.create_hydrated_bundle()
        api = v0_5.StockTransactionResource()

        bundle = api.dehydrate(bm)
        self.assertEqual(bundle.data['product_name'], 'name')
        self.assertEqual(bundle.data['transaction_date'], 'date')

    @classmethod
    def create_hydrated_bundle(cls):
        bm = mock.Mock()
        bm.data = {}
        bm.obj = mock.Mock()
        bm.obj.sql_product = mock.Mock()
        bm.obj.sql_product.name = 'name'
        bm.obj.report = mock.Mock()
        bm.obj.report.date = 'date'
        return bm


class TestGroupResource(APIResourceTest):
    resource = v0_5.GroupResource
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super(TestGroupResource, cls).setUpClass()
        cls.group = Group({"name": "test"})
        cls.group.domain = 'test_domain'
        cls.group.save()

    @classmethod
    def tearDownClass(cls):
        super(TestGroupResource, cls).tearDownClass()
        cls.group.delete()

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

    def test_patch_list_no_object_collection(self):
        api = v0_5.GroupResource()
        body = {"some": {
                    "irrelevant": "data"
                }}
        request = RequestFactory().post(self.list_endpoint,
                                        data=json.dumps(body),
                                        content_type='application/json')

        request.method = "POST"

        with self.assertRaises(BadRequest):
            api.patch_list(request)

    #TODO: it seems that this methods are invalid and throw attribute error caused by wrong data format
    # passed to serialization

    # def test_patch_list_existing_group(self):
    #     api = v0_5.GroupResource()
    #     body = {"objects": [
    #         {"domain": 'test_domain', "name": "test"}
    #          ]}
    #     request = RequestFactory().post(self.list_endpoint,
    #                                     data=json.dumps(body),
    #                                     content_type='application/json')
    #     print("URL REVERSE: {}".format(self.list_endpoint))
    #     request.method = "POST"
    #     response = api.patch_list(request, domain='test_domain')
    # def test_patch_list_new_group(self):
    #     api = v0_5.GroupResource()
    #     body = {"objects": [
    #         {"domain": 'test_domain', "name": "test_new"}
    #          ]}
    #     request = RequestFactory().post(self.list_endpoint,
    #                                     data=json.dumps(body),
    #                                     content_type='application/json')
    #     print("URL REVERSE: {}".format(self.list_endpoint))
    #     request.method = "POST"
    #     response = api.patch_list(request, domain='test_domain')


class TestUserDomainsResource(APIResourceTest):
    resource = v0_5.UserDomainsResource
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super(TestUserDomainsResource, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(TestUserDomainsResource, cls).tearDownClass()

    @classmethod
    def _get_list_endpoint(cls):
        return cls.list_endpoint

    @property
    def list_endpoint(self):
        return reverse('api_dispatch_list',
            kwargs={
                'api_name': 'global',
                'resource_name': self.resource.Meta.resource_name,
            }
        )

    def test_obj_get_list(self):
        bundle = BundleMock(user=self.user)
        bundle.request.user = self.user
        user_domains = v0_5.UserDomainsResource()
        expected = UserDomain(
            domain_name=self.domain.name,
            project_name=self.domain.hr_name or self.domain.name)
        actual = user_domains.obj_get_list(bundle)

        self.assertEqual(len(actual), 1)
        self.assertIsInstance(actual, list)
        self.assertIn(expected, actual)

    # TODO: Need further check, obj_create method is not implemented in class UserDomainsResource and throws
    #  NotImplementedError
    # def test_dispatch_list(self):
    #     user_domains = self.resource()
    #
    #     body = {
    #         "api_key": self.api_key.key,
    #         "username": self.username}
    #
    #     request = RequestFactory().post(self.list_endpoint,
    #                                     data=json.dumps(body),
    #                                     content_type='application/json')
    #     request.method = "POST"
    #     request.POST = QueryDict('', mutable=True)
    #     request.POST.update(body)
    #     request.user = self.user
    #     request.api_key = self.api_key.key
    #
    #     result = user_domains.dispatch_list(request=request,
    #                                         api_key=self.api_key.key,
    #                                         username=self.user.name,
    #                                         type="user")


class TestDomainCases(APIResourceTest):
    resource = v0_5.DomainCases
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super(TestDomainCases, cls).setUpClass()
        cls.create_app()
        cls.create_case()

    @classmethod
    def tearDownClass(cls):
        cls.case.delete()
        cls.application.delete_app()
        super(TestDomainCases, cls).tearDownClass()

    @classmethod
    def create_app(cls):
        cls.app_name = 'Application'

        cls.application = Application.new_app(cls.domain.name, cls.app_name)
        cls.application.save()

    @classmethod
    def create_case(cls):
        cls.case = create_and_save_a_case(cls.domain.name, case_id=uuid.uuid4().hex, case_name='test case')
        cls.case.type = 'type'
        cls.case.save()

    @mock.patch('corehq.apps.api.resources.v0_5.get_case_types_for_domain_es')
    def test_obj_get_list(self, elastic):
        bundle = BundleMock(user=self.user, application_id=self.application.id)
        bundle.request.user = self.user
        user_domains = v0_5.DomainCases()
        elastic.return_value = {'t1', 't2'}
        actual = user_domains.obj_get_list(bundle, domain=self.domain.name)
        expected = [CaseType('t1', ''), CaseType('t2', '')]

        self.assertEqual(len(actual), 2)
        self.assertIsInstance(actual, list)
        self.assertEqual(expected, actual)
        elastic.assert_called_with(self.domain.name)


class TestDomainUsernames(APIResourceTest):
    resource = v0_5.DomainUsernames
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super(TestDomainUsernames, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(TestDomainUsernames, cls).tearDownClass()

    def test_get_usernames(self):
        body = {
            "domain": self.domain.name,
            "username": self.username}

        request = RequestFactory().post(self.list_endpoint,
                                        data=json.dumps(body),
                                        content_type='application/json')
        request.method = "POST"
        request.POST = QueryDict('', mutable=True)
        request.POST.update(body)
        request.user = self.user
        bundle = BundleMock()
        bundle.request = request

        expected = self.resource().obj_get_list(bundle, domain=self.domain.name)
        actual = [UserInfo(self.user.userID, self.username.split('@')[0])]

        self.assertEqual(expected, actual)
