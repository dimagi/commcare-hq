from __future__ import absolute_import
from __future__ import unicode_literals
import base64
import json
import uuid
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime

from django.conf import settings
from django.urls import reverse
from django.http import QueryDict
from django.test import TestCase
from django.utils.http import urlencode

from tastypie import fields
from tastypie.models import ApiKey
from tastypie.resources import Resource

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import post_case_blocks
from corehq.apps.api.models import ESCase, ESXFormInstance
from corehq.apps.userreports.models import ReportConfiguration, \
    DataSourceConfiguration
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.pillows.case import transform_case_for_elasticsearch
from couchforms.models import XFormInstance
from dimagi.utils.parsing import json_format_datetime

from django_prbac.models import Role

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustment
)
from corehq.apps.api.es import ElasticAPIQuerySet
from corehq.apps.api.fields import ToManyDocumentsField, ToOneDocumentField, UseIfRequested, ToManyDictField
from corehq.apps.api.resources import v0_4, v0_5
from corehq.apps.api.util import get_obj, object_does_not_exist
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.motech.repeaters.models import FormRepeater, CaseRepeater, ShortFormRepeater
from corehq.apps.fixtures.resources.v0_1 import InternalFixtureResource
from corehq.apps.locations.resources.v0_1 import InternalLocationResource
from custom.ilsgateway.resources.v0_1 import ILSLocationResource
from custom.ewsghana.resources.v0_1 import EWSLocationResource
from corehq.apps.users.analytics import update_analytics_indexes
from corehq.apps.users.models import CommCareUser, WebUser, UserRole, Permissions
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.pillows.reportxform import transform_xform_for_report_forms_index
from corehq.pillows.xform import transform_xform_for_elasticsearch
from custom.hope.models import CC_BIHAR_PREGNANCY
from six.moves import range


class FakeXFormES(object):
    """
    A mock of XFormES that will return the docs that have been
    added regardless of the query.
    """

    def __init__(self, wrapper=None):
        self.wrapper = wrapper
        self.docs = OrderedDict()
        self.queries = []

    def add_doc(self, id, doc):
        id = doc.get('_id', id)
        self.docs[id] = doc

    def run_query(self, query):
        self.queries.append(query)

        start = query.get('from', 0)
        end = (query['size'] + start) if 'size' in query else None
        
        return {
            'hits': {
                'total': len(self.docs),
                'hits': [{'_source': doc} for doc in list(self.docs.values())[start:end]]
            }
        }

    def get_document(self, doc_id):
        try:
            doc = self.docs[doc_id]
        except KeyError:
            raise object_does_not_exist('document', doc_id)

        if self.wrapper:
            return self.wrapper(doc)
        return doc


class APIResourceTest(TestCase):
    """
    Base class for shared API tests. Sets up a domain and user and provides
    some helper methods and properties for accessing the API
    """
    resource = None # must be set by subclasses
    api_name = 'v0.4' # can be overridden by subclasses
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(APIResourceTest, cls).setUpClass()

        Role.get_cache().clear()
        cls.domain = Domain.get_or_create_with_name('qwerty', is_active=True)
        cls.list_endpoint = cls._get_list_endpoint()
        cls.username = 'rudolph@qwerty.commcarehq.org'
        cls.password = '***'
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.password)
        cls.user.set_role(cls.domain.name, 'admin')
        cls.user.save()

        cls.account = BillingAccount.get_or_create_account_by_domain(cls.domain.name, created_by="automated-test")[0]
        plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        cls.subscription = Subscription.new_domain_subscription(cls.account, cls.domain.name, plan)
        cls.subscription.is_active = True
        cls.subscription.save()

        cls.api_key, _ = ApiKey.objects.get_or_create(user=WebUser.get_django_user(cls.user))

    @classmethod
    def _get_list_endpoint(cls):
        return reverse('api_dispatch_list',
                kwargs=dict(domain=cls.domain.name,
                            api_name=cls.api_name,
                            resource_name=cls.resource._meta.resource_name))

    @classmethod
    def tearDownClass(cls):
        cls.api_key.delete()
        cls.user.delete()

        SubscriptionAdjustment.objects.all().delete()

        if cls.subscription:
            cls.subscription.delete()

        if cls.account:
            cls.account.delete()

        for domain in Domain.get_all():
            domain.delete()

        super(APIResourceTest, cls).tearDownClass()

    def single_endpoint(self, id):
        return reverse('api_dispatch_detail', kwargs=dict(domain=self.domain.name,
                                                          api_name=self.api_name,
                                                          resource_name=self.resource._meta.resource_name,
                                                          pk=id))

    def _api_url(self, url, username=None):
        if 'api_key' in url:
            return url

        username = username or self.username
        api_key = self.api_key.key
        if username != self.username:
            web_user = WebUser.get_by_username(username)
            api_key, _ = ApiKey.objects.get_or_create(user=WebUser.get_django_user(web_user))
            api_key = api_key.key

        api_params = urlencode({'username': username, 'api_key': api_key})

        if "?" in url:
            api_url = "%s&%s" % (url, api_params)
        else:
            api_url = "%s?%s" % (url, api_params)
        return api_url

    def _assert_auth_get_resource(self, url, username=None, password=None, failure_code=401):
        """
        This tests that the given URL fails when accessed via sessions and returns the response
        obtained via using API auth. It's callers' responsibility to test resource specific logic
        using response returned.

        The user authentication is attempted via default self.username creds, other creds can be passed
        via username and password kwargs
        """
        username = username or self.username
        password = password or self.password

        # session based auth should fail
        self.client.login(username=username, password=password)
        response = self.client.get(url)
        self.assertEqual(response.status_code, failure_code)

        # api_key auth should succeed, caller can check for expected code
        api_url = self._api_url(url, username)
        response = self.client.get(api_url)
        return response

    def _assert_auth_post_resource(self, url, post_data, content_type='application/json', method="POST",
                                   failure_code=401):
        """
        See docstring for _assert_auth_get_resource()
        """
        # session based auth should fail
        self.client.login(username=self.username, password=self.password)
        if method == "POST":
            response = self.client.post(url, post_data, content_type=content_type)
        elif method == "PUT":
            response = self.client.put(url, post_data, content_type=content_type)
        self.assertEqual(response.status_code, failure_code)

        # api_key auth should succeed, caller should check expected response status and content
        api_url = self._api_url(url)
        if method == "POST":
            response = self.client.post(api_url, post_data, content_type=content_type)
        elif method == "PUT":
            response = self.client.put(api_url, post_data, content_type=content_type)
        return response


class TestXFormInstanceResource(APIResourceTest):
    """
    Tests the XFormInstanceResource, currently only v0_4

    TODO: Provide tests for each version, especially for those aspects
    which differ between versions. They should call into reusable tests
    for the functionality that is not different.
    """
    resource = v0_4.XFormInstanceResource

    def _test_es_query(self, url_params, expected_query):

        fake_xform_es = FakeXFormES()

        prior_run_query = fake_xform_es.run_query

        # A bit of a hack since none of Python's mocking libraries seem to do basic spies easily...
        def mock_run_query(es_query):
            self.assertEqual(sorted(es_query['filter']['and']), expected_query)
            return prior_run_query(es_query)

        fake_xform_es.run_query = mock_run_query
        v0_4.MOCK_XFORM_ES = fake_xform_es

        response = self._assert_auth_get_resource('%s?%s' % (self.list_endpoint, urlencode(url_params)))
        self.assertEqual(response.status_code, 200)

    def test_get_list(self):
        """
        Any form in the appropriate domain should be in the list from the API.
        """
        # The actual infrastructure involves saving to CouchDB, having PillowTop
        # read the changes and write it to ElasticSearch.

        # In order to test just the API code, we set up a fake XFormES (this should
        # really be a parameter to the XFormInstanceResource constructor)
        # and write the translated form directly; we are not trying to test
        # the ptop infrastructure.

        #the pillow is set to offline mode - elasticsearch not needed to validate
        fake_xform_es = FakeXFormES()
        v0_4.MOCK_XFORM_ES = fake_xform_es

        backend_form = XFormInstance(
            xmlns='fake-xmlns',
            domain=self.domain.name,
            received_on=datetime.utcnow(),
            edited_on=datetime.utcnow(),
            form={
                '#type': 'fake-type',
                '@xmlns': 'fake-xmlns',
                'meta': {'userID': 'metadata-user-id'},
            },
            auth_context={
                'user_id': 'auth-user-id',
                'domain': self.domain.name,
                'authenticated': True,
            },
        )
        backend_form.save()
        self.addCleanup(backend_form.delete)
        translated_doc = transform_xform_for_elasticsearch(backend_form.to_json())
        fake_xform_es.add_doc(translated_doc['_id'], translated_doc)

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_forms = json.loads(response.content)['objects']
        self.assertEqual(len(api_forms), 1)

        api_form = api_forms[0]
        self.assertEqual(api_form['form']['@xmlns'], backend_form.xmlns)
        self.assertEqual(api_form['received_on'], json_format_datetime(backend_form.received_on))
        self.assertEqual(api_form['metadata']['userID'], 'metadata-user-id')
        self.assertEqual(api_form['edited_by_user_id'], 'auth-user-id')

    def test_get_list_xmlns(self):
        """
        Forms can be filtered by passing ?xmlns=<xmlns>

        Since we not testing ElasticSearch, we only test that the proper query is generated.
        """
        expected = [
            {'term': {'doc_type': 'xforminstance'}},
            {'term': {'domain.exact': 'qwerty'}},
            {'term': {'xmlns.exact': 'foo'}}
        ]
        self._test_es_query({'xmlns': 'foo'}, expected)

    def test_get_list_received_on(self):
        """
        Forms can be filtered by passing ?recieved_on_start=<date>&received_on_end=<date>

        Since we not testing ElasticSearch, we only test that the proper query is generated.
        """

        start_date = datetime(1969, 6, 14)
        end_date = datetime(2011, 1, 2)
        expected = [
            {'range': {'received_on': {'from': start_date.isoformat()}}},
            {'range': {'received_on': {'to': end_date.isoformat()}}},
            {'term': {'doc_type': 'xforminstance'}},
            {'term': {'domain.exact': 'qwerty'}},
        ]
        params = {
            'received_on_end': end_date.isoformat(),
            'received_on_start': start_date.isoformat(),
        }
        self._test_es_query(params, expected)

    def test_get_list_ordering(self):
        '''
        Forms can be ordering ascending or descending on received_on; by default
        ascending.
        '''

        fake_xform_es = FakeXFormES()

        # A bit of a hack since none of Python's mocking libraries seem to do basic spies easily...
        prior_run_query = fake_xform_es.run_query
        queries = []

        def mock_run_query(es_query):
            queries.append(es_query)
            return prior_run_query(es_query)

        fake_xform_es.run_query = mock_run_query
        v0_4.MOCK_XFORM_ES = fake_xform_es

        # Runs *2* queries
        response = self._assert_auth_get_resource('%s?order_by=received_on' % self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(queries[0]['sort'], [{'received_on': 'asc'}])
        # Runs *2* queries
        response = self._assert_auth_get_resource('%s?order_by=-received_on' % self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(queries[2]['sort'], [{'received_on': 'desc'}])

    def test_get_list_archived(self):
        expected = [
            {'or': [
                {'term': {'doc_type': 'xforminstance'}},
                {'term': {'doc_type': 'xformarchived'}}
            ]},
            {'term': {'domain.exact': 'qwerty'}},
        ]
        self._test_es_query({'include_archived': 'true'}, expected)

    @run_with_all_backends
    def test_fetching_xform_cases(self):
        fake_xform_es = FakeXFormES(ESXFormInstance)
        v0_4.MOCK_XFORM_ES = fake_xform_es

        # Create an xform that touches a case
        case_id = uuid.uuid4().hex
        form = submit_case_blocks(
            CaseBlock(
                case_id=case_id,
                create=True,
            ).as_string(),
            self.domain.name
        )[0]

        fake_xform_es.add_doc(form.form_id, transform_xform_for_elasticsearch(form.to_json()))

        # Fetch the xform through the API
        response = self._assert_auth_get_resource(self.single_endpoint(form.form_id) + "?cases__full=true")
        self.assertEqual(response.status_code, 200)
        cases = json.loads(response.content)['cases']

        # Confirm that the case appears in the resource
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]['id'], case_id)


class TestCommCareCaseResource(APIResourceTest):
    """
    Tests the CommCareCaseREsource, currently only v0_4
    """
    resource = v0_4.CommCareCaseResource

    def test_get_list(self):
        """
        Any case in the appropriate domain should be in the list from the API.
        """

        # The actual infrastructure involves saving to CouchDB, having PillowTop
        # read the changes and write it to ElasticSearch.

        #the pillow is set to offline mode - elasticsearch not needed to validate
        fake_case_es = FakeXFormES()
        v0_4.MOCK_CASE_ES = fake_case_es

        modify_date = datetime.utcnow()

        backend_case = CommCareCase(server_modified_on=modify_date, domain=self.domain.name)
        backend_case.save()
        self.addCleanup(backend_case.delete)

        translated_doc = transform_case_for_elasticsearch(backend_case.to_json())

        fake_case_es.add_doc(translated_doc['_id'], translated_doc)

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_cases = json.loads(response.content)['objects']
        self.assertEqual(len(api_cases), 1)

        api_case = api_cases[0]
        self.assertEqual(api_case['server_date_modified'], json_format_datetime(backend_case.server_modified_on))

    @run_with_all_backends
    def test_parent_and_child_cases(self):
        fake_case_es = FakeXFormES(ESCase)
        v0_4.MOCK_CASE_ES = fake_case_es

        # Create cases
        parent_case_id = uuid.uuid4().hex
        parent_type = 'parent_case_type'
        parent_case = submit_case_blocks(
            CaseBlock(
                case_id=parent_case_id,
                create=True,
                case_type=parent_type,
            ).as_string(),
            self.domain.name
        )[1][0]
        child_case_id = uuid.uuid4().hex
        child_case = submit_case_blocks(
            CaseBlock(
                case_id=child_case_id,
                create=True,
                index={'parent': (parent_type, parent_case_id)}
            ).as_string(),
            self.domain.name
        )[1][0]

        fake_case_es.add_doc(parent_case_id, transform_case_for_elasticsearch(parent_case.to_json()))
        fake_case_es.add_doc(child_case_id, transform_case_for_elasticsearch(child_case.to_json()))

        # Fetch the child case through the API

        response = self._assert_auth_get_resource(self.single_endpoint(child_case_id) + "?parent_cases__full=true")
        self.assertEqual(
            response.status_code,
            200,
            "Status code was not 200. Response content was {}".format(response.content)
        )
        parent_cases = list(json.loads(response.content)['parent_cases'].values())

        # Confirm that the case appears in the resource
        self.assertEqual(len(parent_cases), 1)
        self.assertEqual(parent_cases[0]['id'], parent_case_id)

        # Fetch the parent case through the API

        response = self._assert_auth_get_resource(self.single_endpoint(parent_case_id) + "?child_cases__full=true")
        self.assertEqual(
            response.status_code,
            200,
            "Status code was not 200. Response content was {}".format(response.content)
        )
        child_cases = list(json.loads(response.content)['child_cases'].values())

        # Confirm that the case appears in the resource
        self.assertEqual(len(child_cases), 1)
        self.assertEqual(child_cases[0]['id'], child_case_id)

    def test_no_subscription(self):
        """
        Tests authorization function properly blocks domains without proper subscription
        :return:
        """
        community_domain = Domain.get_or_create_with_name('dvorak', is_active=True)
        new_user = WebUser.create(community_domain.name, 'test', 'testpass')
        new_user.save()

        self.addCleanup(new_user.delete)
        self.addCleanup(community_domain.delete)

        response = self._assert_auth_get_resource(self.list_endpoint, username='test', password='testpass')
        self.assertEqual(response.status_code, 403)

    def test_superuser(self):
        """
        Tests superuser overrides authorization
        :return:
        """
        community_domain = Domain.get_or_create_with_name('dvorak', is_active=True)
        new_user = WebUser.create(community_domain.name, 'test', 'testpass', is_superuser=True)
        new_user.save()

        self.addCleanup(new_user.delete)
        self.addCleanup(community_domain.delete)

        response = self._assert_auth_get_resource(self.list_endpoint, username='test', password='testpass')
        self.assertEqual(response.status_code, 200)


class TestHOPECaseResource(APIResourceTest):
    """
    Tests the HOPECaseREsource, currently only v0_4, just to make sure
    it does not crash right away
    """
    resource = v0_4.HOPECaseResource

    def test_get_list(self):
        """
        Any case in the appropriate domain should be in the list from the API.
        """

        # The actual infrastructure involves saving to CouchDB, having PillowTop
        # read the changes and write it to ElasticSearch.

        fake_case_es = FakeXFormES()
        v0_4.MOCK_CASE_ES = fake_case_es

        modify_date = datetime.utcnow()

        backend_case = CommCareCase(server_modified_on=modify_date, domain=self.domain.name)
        backend_case.type = CC_BIHAR_PREGNANCY
        backend_case.save()
        self.addCleanup(backend_case.delete)

        translated_doc = transform_case_for_elasticsearch(backend_case.to_json())

        fake_case_es.add_doc(translated_doc['_id'], translated_doc)

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_cases = json.loads(response.content)['objects']
        self.assertEqual(len(api_cases), 2)

        api_case = api_cases['mother_lists'][0]
        self.assertEqual(api_case['id'], backend_case.case_id)


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
            "edit_locations": True,
            "edit_data": True,
            "edit_web_users": True,
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
        for perm in ['edit_web_users', 'edit_commcare_users', 'edit_locations',
                     'edit_data', 'edit_apps', 'view_reports']:
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
        self.assertEqual(response.content, '{"error": "An admin can have only one role : Admin"}')

    def test_create_with_invalid_non_admin_role(self):
        user_json = deepcopy(self.default_user_json)
        user_json['is_admin'] = False
        user_json["role"] = 'Jack of all trades'
        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json',
                                                   failure_code=400)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, '{"error": "Invalid User Role Jack of all trades"}')

    def test_create_with_missing_non_admin_role(self):
        user_json = deepcopy(self.default_user_json)
        user_json['is_admin'] = False
        user_json.pop("role")
        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   json.dumps(user_json),
                                                   content_type='application/json',
                                                   failure_code=400)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, '{"error": "Please assign role for non admin user"}')

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


class TestRepeaterResource(APIResourceTest):
    """
    Basic sanity checking of v0_4.RepeaterResource
    """
    resource = v0_4.RepeaterResource
    repeater_types = [FormRepeater, CaseRepeater, ShortFormRepeater]

    def test_get(self):
        # Add a repeater of various types and check that it comes back
        for cls in self.repeater_types:
            repeater = cls(domain=self.domain.name,
                           url='http://example.com/forwarding/{cls}'.format(cls=cls.__name__))
            repeater.save()
            self.addCleanup(repeater.delete)
            backend_id = repeater._id
            response = self._assert_auth_get_resource(self.single_endpoint(backend_id))
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.assertEqual(result['id'], backend_id)
            self.assertEqual(result['url'], repeater.url)
            self.assertEqual(result['domain'], repeater.domain)
            self.assertEqual(result['type'], cls.__name__)

    def test_get_list(self):

        # Add a form repeater and check that it comes back
        form_repeater = FormRepeater(domain=self.domain.name, url='http://example.com/forwarding/form')
        form_repeater.save()
        self.addCleanup(form_repeater.delete)
        backend_id = form_repeater._id

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_repeaters = json.loads(response.content)['objects']
        self.assertEqual(len(api_repeaters), 1)
        self.assertEqual(api_repeaters[0]['id'], backend_id)
        self.assertEqual(api_repeaters[0]['url'], form_repeater.url)
        self.assertEqual(api_repeaters[0]['domain'], form_repeater.domain)
        self.assertEqual(api_repeaters[0]['type'], 'FormRepeater')

        # Add a case repeater and check that both come back
        case_repeater = CaseRepeater(domain=self.domain.name, url='http://example.com/forwarding/case')
        case_repeater.save()
        self.addCleanup(case_repeater.delete)
        backend_id = case_repeater._id

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_repeaters = json.loads(response.content)['objects']
        self.assertEqual(len(api_repeaters), 2)

        api_case_repeater = filter(lambda r: r['type'] == 'CaseRepeater', api_repeaters)[0]
        self.assertEqual(api_case_repeater['id'], case_repeater._id)
        self.assertEqual(api_case_repeater['url'], case_repeater.url)
        self.assertEqual(api_case_repeater['domain'], case_repeater.domain)

    def test_create(self):

        for cls in self.repeater_types:
            self.assertEqual(0, len(cls.by_domain(self.domain.name)))

            repeater_json = {
                "domain": self.domain.name,
                "type": cls.__name__,
                "url": "http://example.com/forwarding/{cls}".format(cls=cls.__name__),
            }
            response = self._assert_auth_post_resource(self.list_endpoint,
                                        json.dumps(repeater_json),
                                        content_type='application/json')
            self.assertEqual(response.status_code, 201, response.content)
            [repeater_back] = cls.by_domain(self.domain.name)
            self.addCleanup(repeater_back.delete)
            self.assertEqual(repeater_json['domain'], repeater_back.domain)
            self.assertEqual(repeater_json['type'], repeater_back.doc_type)
            self.assertEqual(repeater_json['url'], repeater_back.url)

    def test_update(self):

        for cls in self.repeater_types:
            repeater = cls(domain=self.domain.name,
                           url='http://example.com/forwarding/{cls}'.format(cls=cls.__name__))
            repeater.save()
            self.addCleanup(repeater.delete)
            backend_id = repeater._id
            repeater_json = {
                "domain": self.domain.name,
                "type": cls.__name__,
                "url": "http://example.com/forwarding/modified/{cls}".format(cls=cls.__name__),
            }
            response = self._assert_auth_post_resource(self.single_endpoint(backend_id),
                                                       json.dumps(repeater_json),
                                                       content_type='application/json',
                                                       method='PUT')
            self.assertEqual(response.status_code, 204, response.content)
            self.assertEqual(1, len(cls.by_domain(self.domain.name)))
            modified = cls.get(backend_id)
            self.assertTrue('modified' in modified.url)


class TestReportPillow(TestCase):

    def test_xformPillowTransform(self):
        """
        Test to make sure report xform and reportxform pillows strip the appVersion dict to match the
        mappings
        """
        transform_functions = [transform_xform_for_report_forms_index, transform_xform_for_elasticsearch]
        bad_appVersion = {
            "_id": "foo",
            "domain": settings.ES_XFORM_FULL_INDEX_DOMAINS[0],
            'received_on': "2013-09-20T01:33:12Z",
            "form": {
                "meta": {
                    "@xmlns": "http://openrosa.org/jr/xforms",
                    "username": "someuser",
                    "instanceID": "foo",
                    "userID": "some_user_id",
                    "timeEnd": "2013-09-20T01:33:12Z",
                    "appVersion": {
                        "@xmlns": "http://commcarehq.org/xforms",
                        "#text": "CCODK:\"2.5.1\"(11126). v236 CC2.5b[11126] on April-15-2013"
                    },
                    "timeStart": "2013-09-19T01:13:20Z",
                    "deviceID": "somedevice"
                }
            }
        }
        for fn in transform_functions:
            cleaned = fn(bad_appVersion)
            self.assertFalse(isinstance(cleaned['form']['meta']['appVersion'], dict))
            self.assertTrue(isinstance(cleaned['form']['meta']['appVersion'], str))
            self.assertTrue(cleaned['form']['meta']['appVersion'], "CCODK:\"2.5.1\"(11126). v236 CC2.5b[11126] on April-15-2013")


class TestElasticAPIQuerySet(TestCase):
    '''
    Tests the ElasticAPIQuerySet for appropriate slicing, etc
    '''

    def test_slice(self):
        es = FakeXFormES()
        for i in range(0, 1300):
            es.add_doc(i, {'i': i})
        
        queryset = ElasticAPIQuerySet(es_client=es, payload={})
        qs_slice = list(queryset[3:7])

        self.assertEqual(es.queries[0]['from'], 3)
        self.assertEqual(es.queries[0]['size'], 4)
        self.assertEqual(len(qs_slice), 4)

        queryset = ElasticAPIQuerySet(es_client=es, payload={})
        qs_slice = list(queryset[10:20])

        self.assertEqual(es.queries[1]['from'], 10)
        self.assertEqual(es.queries[1]['size'], 10)
        self.assertEqual(len(qs_slice), 10)

        queryset = ElasticAPIQuerySet(es_client=es, payload={})
        qs_slice = list(queryset[500:1000])
        
        self.assertEqual(es.queries[2]['from'], 500)
        self.assertEqual(es.queries[2]['size'], 500)
        self.assertEqual(len(qs_slice), 500)

    def test_order_by(self):
        es = FakeXFormES()
        for i in range(0, 1300):
            es.add_doc(i, {'i': i})
        
        queryset = ElasticAPIQuerySet(es_client=es, payload={})
        qs_asc = list(queryset.order_by('foo'))
        self.assertEqual(es.queries[0]['sort'], [{'foo': 'asc'}])

        qs_desc = list(queryset.order_by('-foo'))
        self.assertEqual(es.queries[1]['sort'], [{'foo': 'desc'}])

        qs_overwrite = list(queryset.order_by('bizzle').order_by('-baz'))
        self.assertEqual(es.queries[2]['sort'], [{'baz': 'desc'}])

        qs_multi = list(queryset.order_by('one', '-two', 'three'))
        self.assertEqual(es.queries[3]['sort'], [{'one': 'asc'}, {'two': 'desc'}, {'three': 'asc'}])


class ToManySourceModel(object):

    def __init__(self, other_model_ids, other_model_dict):
        self.other_model_dict = other_model_dict
        self.other_model_ids = other_model_ids

    @property
    def other_models(self):
        return [self.other_model_dict.get(id) for id in self.other_model_ids]
    

class ToManyDestModel(object):

    def __init__(self, id):
        self.id = id
    

class ToManySourceResource(Resource):
    other_model_ids = fields.ListField(attribute='other_model_ids')
    other_models = ToManyDocumentsField('corehq.apps.api.tests.ToManyDestResource', attribute='other_models')

    def __init__(self, objs):
        super(ToManySourceResource, self).__init__()
        self.objs = objs

    def obj_get_list(self):
        return self.objs

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).other_model_ids
        }

    class Meta:
        model_class = ToManySourceModel


class ToManyDestResource(Resource):
    id = fields.CharField(attribute='id')

    class Meta:
        model_class = ToManyDestModel

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).id
        }


class TestToManyDocumentsField(TestCase):
    '''
    Basic test that ToMany dehydrated alright
    '''
    
    def test_requested_use_in(self):
        dest_objs = {
            'foo': ToManyDestModel('foo'),
            'bar': ToManyDestModel('bar'),
            'baz': ToManyDestModel('baz'),
        }
        
        source_objs = [
            ToManySourceModel(other_model_ids=['foo', 'bar'], other_model_dict=dest_objs),
            ToManySourceModel(other_model_ids=['bar', 'baz'], other_model_dict=dest_objs)
        ]

        source_resource = ToManySourceResource(source_objs)

        bundle = source_resource.build_bundle(obj=source_objs[0])
        dehydrated_bundle = source_resource.full_dehydrate(bundle)

        self.assertTrue('other_models' in dehydrated_bundle.data)
        self.assertEqual([other['id'] for other in dehydrated_bundle.data['other_models']], ['foo', 'bar'])

        bundle = source_resource.build_bundle(obj=source_objs[1])
        dehydrated_bundle = source_resource.full_dehydrate(bundle)

        self.assertEqual([other['id'] for other in dehydrated_bundle.data['other_models']], ['bar', 'baz'])

        
class ToManyDictSourceModel(object):

    def __init__(self, other_model_ids, other_model_dict):
        self.other_model_dict = other_model_dict
        self.other_model_ids = other_model_ids

    @property
    def other_models(self):
        return dict([(key, self.other_model_dict.get(id)) for key, id in self.other_model_ids.items()])
    

class ToManyDictDestModel(object):

    def __init__(self, id):
        self.id = id


class ToManyDictSourceResource(Resource):
    other_model_ids = fields.ListField(attribute='other_model_ids')
    other_models = ToManyDictField('corehq.apps.api.tests.ToManyDictDestResource', attribute='other_models')

    def __init__(self, objs):
        super(ToManyDictSourceResource, self).__init__()
        self.objs = objs

    def obj_get_list(self):
        return self.objs

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).other_model_ids
        }

    class Meta:
        model_class = ToManyDictSourceModel


class ToManyDictDestResource(Resource):
    id = fields.CharField(attribute='id')

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).id
        }

    class Meta:
        model_class = ToManyDictDestModel


class TestToManyDictField(TestCase):
    '''
    Basic test that ToMany dehydrated alright
    '''
    
    def test_dehydrate(self):
        dest_objs = {
            'foo': ToManyDictDestModel('foo'),
            'bar': ToManyDictDestModel('bar'),
            'baz': ToManyDictDestModel('baz'),
        }
        
        source_objs = [
            ToManyDictSourceModel(other_model_ids={ 'first_other': 'foo', 'second_other': 'bar'}, other_model_dict=dest_objs),
            ToManyDictSourceModel(other_model_ids={ 'first_other': 'bar', 'second_other': 'baz'}, other_model_dict=dest_objs)
        ]

        source_resource = ToManyDictSourceResource(source_objs)

        bundle = source_resource.build_bundle(obj=source_objs[0])
        dehydrated_bundle = source_resource.full_dehydrate(bundle)

        self.assertTrue('other_models' in dehydrated_bundle.data)
        self.assertEqual(dehydrated_bundle.data['other_models']['first_other']['id'], 'foo')
        self.assertEqual(dehydrated_bundle.data['other_models']['second_other']['id'], 'bar')

        bundle = source_resource.build_bundle(obj=source_objs[1])
        dehydrated_bundle = source_resource.full_dehydrate(bundle)

        self.assertEqual(dehydrated_bundle.data['other_models']['first_other']['id'], 'bar')
        self.assertEqual(dehydrated_bundle.data['other_models']['second_other']['id'], 'baz')


class ToOneSourceModel(object):

    def __init__(self, other_model_id, other_model_dict):
        self.other_model_dict = other_model_dict
        self.other_model_id = other_model_id

    @property
    def other_model(self):
        return self.other_model_dict.get(self.other_model_id)
    

class ToOneDestModel(object):

    def __init__(self, id):
        self.id = id
    

class ToOneSourceResource(Resource):
    other_model_id = fields.ListField(attribute='other_model_id')
    other_model = ToOneDocumentField('corehq.apps.api.tests.ToOneDestResource', attribute='other_model')

    def __init__(self, objs):
        super(ToOneSourceResource, self).__init__()
        self.objs = objs

    def obj_get_list(self):
        return self.objs

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).other_model_id
        }

    class Meta:
        model_class = ToOneSourceModel


class ToOneDestResource(Resource):
    id = fields.CharField(attribute='id')

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).id
        }

    class Meta:
        model_class = ToOneDestModel


class TestToOneDocumentField(TestCase):
    '''
    Basic test of the <fieldname>__full
    '''
    
    def test_requested_use_in(self):
        dest_objs = {
            'foo': ToOneDestModel('foo'),
            'bar': ToOneDestModel('bar'),
            'baz': ToOneDestModel('baz'),
        }
        
        source_objs = [
            ToOneSourceModel(other_model_id='foo', other_model_dict=dest_objs),
            ToOneSourceModel(other_model_id='bar', other_model_dict=dest_objs)
        ]

        source_resource = ToOneSourceResource(source_objs)

        bundle = source_resource.build_bundle(obj=source_objs[0])
        dehydrated_bundle = source_resource.full_dehydrate(bundle)

        self.assertEqual(dehydrated_bundle.data['other_model']['id'], 'foo')

        bundle = source_resource.build_bundle(obj=source_objs[1])
        dehydrated_bundle = source_resource.full_dehydrate(bundle)

        self.assertEqual(dehydrated_bundle.data['other_model']['id'], 'bar')

        
class UseIfRequestedModel(object):

    def __init__(self, id):
        self.id = id


class UseIfRequestedTestResource(Resource):
    something = UseIfRequested(fields.CharField(attribute='id'))

    def __init__(self, objs):
        super(UseIfRequestedTestResource, self).__init__()
        self.objs = objs

    def obj_get_list(self):
        return self.objs

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).id
        }

    class Meta:
        model_class = UseIfRequestedModel


class TestUseIfRequested(TestCase):

    def test_requested_use_in(self):
        objs = [
            UseIfRequestedModel(id='foo'),
            UseIfRequestedModel(id='bar')
        ]

        test_resource = UseIfRequestedTestResource(objs)

        bundle = test_resource.build_bundle(obj=objs[0])
        dehydrated_bundle = test_resource.full_dehydrate(bundle)

        self.assertFalse('id' in dehydrated_bundle.data)

        bundle = test_resource.build_bundle(obj=objs[0])
        bundle.request.GET['something__full'] = 'true'
        dehydrated_bundle = test_resource.full_dehydrate(bundle)

        self.assertTrue('something' in dehydrated_bundle.data)
        self.assertEqual(dehydrated_bundle.data['something'], 'foo')


class TestSingleSignOnResource(APIResourceTest):
    resource = v0_4.SingleSignOnResource

    def setUp(self):
        super(TestSingleSignOnResource, self).setUp()
        self.commcare_username = 'webby@qwerty.commcarehq.org'
        self.commcare_password = '*****'
        self.commcare_user = CommCareUser.create(self.domain.name, self.commcare_username, self.commcare_password)

    def tearDown(self):
        self.commcare_user.delete()
        super(TestSingleSignOnResource, self).tearDown()

    def test_web_user_success(self):
        '''
        If correct credentials for a web user are submitted, the response is the profile of that web user
        '''
        response = self.client.post(self.list_endpoint, {'username': self.username, 'password': self.password})
        self.assertEqual(response.status_code, 200)

    def test_commcare_user_success(self):
        '''
        If correct credentials for a commcare user are submitted, the response is the record for that commcare user
        '''
        response = self.client.post(self.list_endpoint,
                                    {'username': self.commcare_username, 'password': self.commcare_password})
        self.assertEqual(response.status_code, 200)

    def test_wrong_domain(self):
        '''
        If correct credentials for a user in a different domain are submitted, the response is forbidden
        '''
        wrong_domain = Domain.get_or_create_with_name('dvorak', is_active=True)
        self.addCleanup(wrong_domain.delete)

        # have to set up subscription for the bad domain or it will fail on authorization
        new_account = BillingAccount.get_or_create_account_by_domain(wrong_domain.name,
                                                                     created_by="automated-test")[0]
        plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        new_subscription = Subscription.new_domain_subscription(new_account, wrong_domain.name, plan)
        new_subscription.is_active = True
        new_subscription.save()
        wrong_list_endpoint = reverse('api_dispatch_list',
                                      kwargs=dict(domain=wrong_domain.name,
                                                  api_name=self.api_name,
                                                  resource_name=self.resource.Meta.resource_name))
        response = self.client.post(wrong_list_endpoint, {'username': self.username, 'password': self.password})
        self.assertEqual(response.status_code, 403)

    def test_wrong_credentials(self):
        '''
        If incorrect password for the correct username and domain pair are submitted, the response is forbidden
        '''
        response = self.client.post(self.list_endpoint, {'username': self.username, 'password': 'bimbizzleboozle'})
        self.assertEqual(response.status_code, 403)

    def test_no_username(self):
        '''
        If no username supplied, 400
        '''
        response = self.client.post(self.list_endpoint, {'password': 'bimbizzleboozle'})
        self.assertEqual(response.status_code, 400)

    def test_no_password(self):
        '''
        If no password supplied, 400
        '''
        response = self.client.post(self.list_endpoint, {'username': self.username})
        self.assertEqual(response.status_code, 400)


class TestGroupResource(APIResourceTest):

    resource = v0_5.GroupResource
    api_name = 'v0.5'

    def test_get_list(self):

        group = Group({"name": "test", "domain": self.domain.name})
        group.save()
        self.addCleanup(group.delete)
        backend_id = group.get_id

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_groups = json.loads(response.content)['objects']
        self.assertEqual(len(api_groups), 1)
        self.assertEqual(api_groups[0]['id'], backend_id)

    def test_get_single(self):

        group = Group({"name": "test", "domain": self.domain.name})
        group.save()
        self.addCleanup(group.delete)
        backend_id = group.get_id

        response = self._assert_auth_get_resource(self.single_endpoint(backend_id))
        self.assertEqual(response.status_code, 200)

        api_groups = json.loads(response.content)
        self.assertEqual(api_groups['id'], backend_id)

    def test_create(self):

        self.assertEqual(0, len(Group.by_domain(self.domain.name)))

        group_json = {
            "case_sharing": True,
            "metadata": {
                "localization": "Ghana"
            },
            "name": "test group",
            "reporting": True,
        }
        response = self._assert_auth_post_resource(self.list_endpoint,
                                    json.dumps(group_json),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)
        [group_back] = Group.by_domain(self.domain.name)
        self.addCleanup(group_back.delete)
        self.assertEqual(group_back.name, "test group")
        self.assertTrue(group_back.reporting)
        self.assertTrue(group_back.case_sharing)
        self.assertEqual(group_back.metadata["localization"], "Ghana")

    def test_update(self):

        group = Group({"name": "test", "domain": self.domain.name})
        group.save()
        self.addCleanup(group.delete)

        group_json = {
            "case_sharing": True,
            "metadata": {
                "localization": "Ghana"
            },
            "name": "test group",
            "reporting": True,
        }

        backend_id = group._id
        response = self._assert_auth_post_resource(self.single_endpoint(backend_id),
                                                   json.dumps(group_json),
                                                   content_type='application/json',
                                                   method='PUT')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(1, len(Group.by_domain(self.domain.name)))
        modified = Group.get(backend_id)
        self.assertEqual(modified.name, "test group")
        self.assertTrue(modified.reporting)
        self.assertTrue(modified.case_sharing)
        self.assertEqual(modified.metadata["localization"], "Ghana")


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
        self.assertEquals(len(users), limit)

        result = self.query(start_at=limit, limit=limit)
        self.assertEqual(result.status_code, 200)
        users = json.loads(result.content)['objects']
        self.assertEquals(len(users), limit)

    def test_basic(self):
        response = self.query()
        self.assertEqual(response.status_code, 200)


class TestApiKey(APIResourceTest):
    """
    Only tests access (200 vs 401). Correctness should be tested elsewhere
    """
    resource = v0_5.WebUserResource
    api_name = 'v0.5'

    def test_get_user(self):
        endpoint = "%s?%s" % (self.single_endpoint(self.user._id),
                              urlencode({
                                  "username": self.user.username,
                                  "api_key": self.api_key.key
                              }))
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 200)

    def test_wrong_api_key(self):
        endpoint = "%s?%s" % (self.single_endpoint(self.user._id),
                              urlencode({
                                  "username": self.user.username,
                                  "api_key": 'blah'
                              }))
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 401)

    def test_wrong_user_api_key(self):
        username = 'blah@qwerty.commcarehq.org'
        password = '***'
        other_user = WebUser.create(self.domain.name, username, password)
        other_user.set_role(self.domain.name, 'admin')
        other_user.save()
        self.addCleanup(other_user.delete)
        django_user = WebUser.get_django_user(other_user)
        other_api_key, _ = ApiKey.objects.get_or_create(user=django_user)
        self.addCleanup(other_api_key.delete)

        endpoint = "%s?%s" % (self.single_endpoint(self.user._id),
                              urlencode({
                                  "username": self.user.username,
                                  "api_key": other_api_key.key
                              }))
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 401)


class InternalTestMixin(object):
    def assert_accessible_via_sessions(self, url):
        # api auth should succeed
        api_url = self._api_url(url, self.username)
        response = self.client.get(api_url)
        self.assertEqual(response.status_code, 200)
        # session auth should also succeed since these are used internally over sessions
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class InternalFixtureResourceTest(APIResourceTest, InternalTestMixin):
    resource = InternalFixtureResource
    api_name = 'v0_5'

    def test_basic(self):
        self.assert_accessible_via_sessions(self.list_endpoint)


class InternalLocationResourceTest(APIResourceTest, InternalTestMixin):
    resource = InternalLocationResource
    api_name = 'v0_5'

    def test_basic(self):
        self.assert_accessible_via_sessions(self.list_endpoint)


class EWSLocationResourceTest(APIResourceTest, InternalTestMixin):
    resource = EWSLocationResource
    api_name = 'v0_3'

    def test_basic(self):
        self.assert_accessible_via_sessions(self.list_endpoint)


class ILSLocationResourceTest(APIResourceTest, InternalTestMixin):
    resource = ILSLocationResource
    api_name = 'v0_3'

    def test_basic(self):
        self.assert_accessible_via_sessions(self.list_endpoint)


class TestSimpleReportConfigurationResource(APIResourceTest):
    resource = v0_5.SimpleReportConfigurationResource
    api_name = "v0.5"

    @classmethod
    def setUpClass(cls):
        super(TestSimpleReportConfigurationResource, cls).setUpClass()

        cls.report_columns = [
            {
                "column_id": 'foo',
                "display": "foo display",
                "type": "field",
                "field": "my_field",
                "aggregation": "simple",
            },
            {
                "column_id": 'bar',
                "display": "bar display",
                "type": "field",
                "field": "my_field",
                "aggregation": "simple",
            },
            {
                "column_id": 'expand',
                "display": "expand display",
                "type": "expanded",
                "field": "my_field",
                "max_expansion": 10,
            }
        ]
        cls.report_filters = [
            {
                'datatype': 'integer',
                'field': 'my_field',
                'type': 'dynamic_choice_list',
                'slug': 'my_field_filter',
            },
            {
                'datatype': 'string',
                'field': 'my_other_field',
                'type': 'dynamic_choice_list',
                'slug': 'my_other_field_filter',
            }
        ]
        cls.report_title = "test report"

        cls.data_source = DataSourceConfiguration(
            domain=cls.domain.name,
            referenced_doc_type="XFormInstance",
            table_id=uuid.uuid4().hex,
        )
        cls.data_source.save()

        cls.report_configuration = ReportConfiguration(
            title=cls.report_title,
            domain=cls.domain.name,
            config_id=cls.data_source._id,
            columns=cls.report_columns,
            filters=cls.report_filters
        )
        cls.report_configuration.save()

        another_report_configuration = ReportConfiguration(
            domain=cls.domain.name, config_id=cls.data_source._id, columns=[], filters=[]
        )
        another_report_configuration.save()

    def test_get_detail(self):
        response = self._assert_auth_get_resource(
            self.single_endpoint(self.report_configuration._id))
        self.assertEqual(response.status_code, 200)
        response_dict = json.loads(response.content)
        filters = response_dict['filters']
        columns = response_dict['columns']

        self.assertEqual(
            set(response_dict.keys()),
            {'resource_uri', 'filters', 'columns', 'id', 'title'}
        )

        self.assertEqual(
            [{
                "column_id": c['column_id'],
                "display": c['display'],
                "type": c['type']
            } for c in self.report_columns],
            columns
        )
        self.assertEqual(
            [{'datatype': x['datatype'], 'slug': x['slug'], 'type': x['type']} for x in self.report_filters],
            filters
        )
        self.assertEqual(response_dict['title'], self.report_title)

    def test_get_list(self):
        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        response_dict = json.loads(response.content)

        self.assertEqual(set(response_dict.keys()), {'meta', 'objects'})
        self.assertEqual(set(response_dict['meta'].keys()), {'total_count'})

        self.assertEqual(response_dict['meta']['total_count'], 2)
        self.assertEqual(len(response_dict['objects']), 2)

    def test_disallowed_methods(self):
        response = self._assert_auth_post_resource(
            self.single_endpoint(self.report_configuration._id),
            {},
            failure_code=405
        )
        self.assertEqual(response.status_code, 405)

    def test_auth(self):

        wrong_domain = Domain.get_or_create_with_name('dvorak', is_active=True)
        new_user = WebUser.create(wrong_domain.name, 'test', 'testpass')
        new_user.save()
        self.addCleanup(wrong_domain.delete)
        self.addCleanup(new_user.delete)

        response = self._assert_auth_get_resource(self.single_endpoint(self.report_configuration._id),
                                                  username='test', password='testpass')
        self.assertEqual(response.status_code, 403)  # 403 is "Forbidden"


class TestConfigurableReportDataResource(APIResourceTest):
    resource = v0_5.ConfigurableReportDataResource
    api_name = "v0.5"

    @classmethod
    def _get_list_endpoint(cls):
        return None

    def single_endpoint(self, id, get_params=None):
        endpoint = reverse('api_dispatch_detail', kwargs=dict(
            domain=self.domain.name,
            api_name=self.api_name,
            resource_name=self.resource._meta.resource_name,
            pk=id,
        ))
        if endpoint:
            endpoint += "?" + urlencode(get_params or {})
        return endpoint

    def setUp(self):
        credentials = base64.b64encode("{}:{}".format(self.username, self.password))
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Basic ' + credentials

    @classmethod
    def setUpClass(cls):
        super(TestConfigurableReportDataResource, cls).setUpClass()

        case_type = "my_case_type"
        cls.field_name = "my_field"
        cls.case_property_values = ["foo", "foo", "bar", "baz"]

        cls.cases = []
        for val in cls.case_property_values:
            id = uuid.uuid4().hex
            case_block = CaseBlock(
                create=True,
                case_id=id,
                case_type=case_type,
                update={cls.field_name: val},
            ).as_xml()
            post_case_blocks([case_block], {'domain': cls.domain.name})
            cls.cases.append(CommCareCase.get(id))

        cls.report_columns = [
            {
                "column_id": cls.field_name,
                "type": "field",
                "field": cls.field_name,
                "aggregation": "simple",
            }
        ]
        cls.report_filters = [
            {
                'datatype': 'string',
                'field': cls.field_name,
                'type': 'dynamic_choice_list',
                'slug': 'my_field_filter',
            }
        ]

        cls.data_source = DataSourceConfiguration(
            domain=cls.domain.name,
            referenced_doc_type="CommCareCase",
            table_id=uuid.uuid4().hex,
            configured_filter={
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "property_name",
                    "property_name": "type"
                },
                "property_value": case_type,
            },
            configured_indicators=[
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": cls.field_name
                    },
                    "column_id": cls.field_name,
                    "display_name": cls.field_name,
                    "datatype": "string"
                },
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": "opened_by"
                    },
                    "column_id": "opened_by",
                    "display_name": "opened_by",
                    "datatype": "string"
                },
            ],
        )
        cls.data_source.validate()
        cls.data_source.save()
        rebuild_indicators(cls.data_source._id)

        cls.report_configuration = ReportConfiguration(
            domain=cls.domain.name,
            config_id=cls.data_source._id,
            aggregation_columns=["doc_id"],
            columns=cls.report_columns,
            filters=cls.report_filters,
        )
        cls.report_configuration.save()

    def test_fetching_data(self):
        response = self.client.get(
            self.single_endpoint(self.report_configuration._id))

        self.assertEqual(response.status_code, 200)
        response_dict = json.loads(response.content)

        self.assertEqual(response_dict["total_records"], len(self.cases))
        self.assertEqual(len(response_dict["data"]), len(self.cases))

    def test_expand_column_infos(self):

        aggregated_report = ReportConfiguration(
            domain=self.domain.name,
            config_id=self.data_source._id,
            aggregation_columns=["opened_by"],
            columns=[
                {
                    "column_id": self.field_name,
                    "type": "field",
                    "field": self.field_name,
                    "aggregation": "expand",
                }
            ],
            filters=[],
        )
        aggregated_report.save()

        response = self.client.get(
            self.single_endpoint(aggregated_report._id))
        response_dict = json.loads(response.content)
        columns = response_dict["columns"]

        for c in columns:
            self.assertIn("expand_column_value", c)
        self.assertSetEqual(set(self.case_property_values), {c['expand_column_value'] for c in columns})


    def test_page_size(self):
        response = self.client.get(
            self.single_endpoint(self.report_configuration._id, {"limit": 1}))
        response_dict = json.loads(response.content)
        self.assertEqual(response_dict["total_records"], len(self.cases))
        self.assertEqual(len(response_dict["data"]), 1)

        response = self.client.get(
            self.single_endpoint(self.report_configuration._id, {"limit": 10000}))
        self.assertEqual(response.status_code, 400)

    def test_page_offset(self):
        response = self.client.get(
            self.single_endpoint(self.report_configuration._id, {"offset": 2}))
        response_dict = json.loads(response.content)
        self.assertEqual(response_dict["total_records"], len(self.cases))
        self.assertEqual(len(response_dict["data"]), len(self.cases) - 2)

    def test_filtering(self):
        response = self.client.get(self.single_endpoint(
            self.report_configuration._id, {"my_field_filter": "foo"})
        )
        response_dict = json.loads(response.content)

        self.assertEqual(response_dict["total_records"], 2)

        response = self.client.get(self.single_endpoint(
            self.report_configuration._id, {"my_field_filter": "bar"})
        )
        response_dict = json.loads(response.content)

        self.assertEqual(response_dict["total_records"], 1)

    def test_next_page_url(self):
        # It's not the last page
        query_dict = QueryDict("", mutable=True)
        query_dict.update({"some_filter": "bar"})
        next = v0_5.ConfigurableReportDataResource(api_name=self.api_name)._get_next_page(
            self.domain.name, "123", 100, 50, 3450, query_dict)
        self.assertEqual(next, self.single_endpoint("123", {"offset": 150, "limit": 50, "some_filter": "bar"}))

        # It's the last page
        next = v0_5.ConfigurableReportDataResource(api_name=self.api_name)._get_next_page(
            self.domain.name, "123", 100, 50, 120, query_dict)
        self.assertEqual(next, "")

    def test_auth(self):
        user_in_wrong_domain_name = 'Mallory'
        user_in_wrong_domain_password = '1337haxor'
        wrong_domain = Domain.get_or_create_with_name('dvorak', is_active=True)
        self.addCleanup(wrong_domain.delete)
        user_in_wrong_domain = WebUser.create(
            wrong_domain.name, user_in_wrong_domain_name, user_in_wrong_domain_password
        )
        self.addCleanup(user_in_wrong_domain.delete)
        user_in_wrong_domain.save()
        credentials = base64.b64encode("{}:{}".format(
            user_in_wrong_domain_name, user_in_wrong_domain_password)
        )
        response = self.client.get(
            self.single_endpoint(self.report_configuration._id),
            HTTP_AUTHORIZATION='Basic ' + credentials
        )
        self.assertEqual(response.status_code, 401)  # 401 is "Unauthorized"
