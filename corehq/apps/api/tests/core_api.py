import json

from datetime import datetime
from django.test import SimpleTestCase, TestCase
from django.test.client import RequestFactory
from unittest.mock import patch

from django.urls import reverse
from django.utils.http import urlencode

from tastypie import fields
from tastypie.resources import Resource

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.api.es import ElasticAPIQuerySet, es_query_from_get_params
from corehq.apps.api.fields import (
    ToManyDictField,
    ToManyDocumentsField,
    ToOneDocumentField,
    UseIfRequested,
)
from corehq.apps.api.resources import v0_4, v0_5
from corehq.apps.api.resources.auth import ApiIdentifier
from corehq.apps.api.util import get_obj
from corehq.apps.domain.models import Domain
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test
from corehq.apps.users.models import CommCareUser, HQApiKey, WebUser
from corehq.util.test_utils import flag_disabled
from no_exceptions.exceptions import Http400
from .utils import APIResourceTest, FakeFormESView


@es_test
class TestElasticAPIQuerySet(TestCase):
    '''
    Tests the ElasticAPIQuerySet for appropriate slicing, etc
    '''

    def test_slice(self):
        es = FakeFormESView()
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
        es = FakeFormESView()
        for i in range(0, 1300):
            es.add_doc(i, {'i': i})

        queryset = ElasticAPIQuerySet(es_client=es, payload={})
        list(queryset.order_by('foo'))
        asc_ = {'missing': '_first', 'order': 'asc'}
        desc_ = {'missing': '_last', 'order': 'desc'}
        self.assertEqual(es.queries[0]['sort'], [{'foo': asc_}])

        list(queryset.order_by('-foo'))
        self.assertEqual(es.queries[1]['sort'], [{'foo': desc_}])

        list(queryset.order_by('bizzle').order_by('-baz'))
        self.assertEqual(es.queries[2]['sort'], [{'baz': desc_}])

        list(queryset.order_by('one', '-two', 'three'))
        self.assertEqual(es.queries[3]['sort'], [{'one': asc_}, {'two': desc_}, {'three': asc_}])

    def test_count(self):
        es = FakeFormESView()
        for i in range(0, 1300):
            es.add_doc(i, {'i': i})

        queryset = ElasticAPIQuerySet(es_client=es, payload={})
        self.assertEqual(queryset.count(), 1300)


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
    other_models = ToManyDocumentsField('corehq.apps.api.tests.core_api.ToManyDestResource',
                                        attribute='other_models')

    def __init__(self, objs):
        super(ToManySourceResource, self).__init__()
        self.objs = objs

    def obj_get_list(self):
        return self.objs

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).other_model_ids
        }

    class Meta(object):
        model_class = ToManySourceModel


class ToManyDestResource(Resource):
    id = fields.CharField(attribute='id')

    class Meta(object):
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
    other_models = ToManyDictField('corehq.apps.api.tests.core_api.ToManyDictDestResource',
                                   attribute='other_models')

    def __init__(self, objs):
        super(ToManyDictSourceResource, self).__init__()
        self.objs = objs

    def obj_get_list(self):
        return self.objs

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).other_model_ids
        }

    class Meta(object):
        model_class = ToManyDictSourceModel


class ToManyDictDestResource(Resource):
    id = fields.CharField(attribute='id')

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).id
        }

    class Meta(object):
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
            ToManyDictSourceModel(other_model_ids={'first_other': 'foo', 'second_other': 'bar'},
                                  other_model_dict=dest_objs),
            ToManyDictSourceModel(other_model_ids={'first_other': 'bar', 'second_other': 'baz'},
                                  other_model_dict=dest_objs)
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
    other_model = ToOneDocumentField('corehq.apps.api.tests.core_api.ToOneDestResource',
                                     attribute='other_model')

    def __init__(self, objs):
        super(ToOneSourceResource, self).__init__()
        self.objs = objs

    def obj_get_list(self):
        return self.objs

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).other_model_id
        }

    class Meta(object):
        model_class = ToOneSourceModel


class ToOneDestResource(Resource):
    id = fields.CharField(attribute='id')

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).id
        }

    class Meta(object):
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

    class Meta(object):
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
        self.commcare_user = CommCareUser.create(self.domain.name, self.commcare_username, self.commcare_password,
                                                 None, None)

    def tearDown(self):
        self.commcare_user.delete(self.domain.name, deleted_by=None)
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
        other_user = WebUser.create(self.domain.name, username, password, None, None)
        other_user.set_role(self.domain.name, 'admin')
        other_user.save()
        self.addCleanup(other_user.delete, self.domain.name, deleted_by=None)
        django_user = WebUser.get_django_user(other_user)
        other_api_key, _ = HQApiKey.objects.get_or_create(user=django_user)
        self.addCleanup(other_api_key.delete)

        endpoint = "%s?%s" % (self.single_endpoint(self.user._id),
                              urlencode({
                                  "username": self.user.username,
                                  "api_key": other_api_key.key
                              }))
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 401)


@es_test
class TestParamstoESFilters(ElasticTestMixin, SimpleTestCase):

    def test_search_param(self):
        # GET param _search can accept a custom query from Data export tool
        self.maxDiff = None
        range_expression = {
            'gte': datetime(2019, 1, 1).isoformat(),
            'lte': datetime(2019, 1, 2).isoformat()
        }
        server_modified_missing = {"missing": {
            "field": "server_modified_on", "null_value": True, "existence": True}
        }
        query = {
            'filter': {
                "or": (
                    {
                        "and": (
                            {
                                "not": server_modified_missing
                            },
                            {
                                "range": {
                                    "server_modified_on": range_expression
                                }
                            }
                        )
                    },
                    {
                        "and": (
                            server_modified_missing,
                            {
                                "range": {
                                    "received_on": range_expression
                                }
                            }
                        )
                    }
                )
            }
        }
        request = RequestFactory().get(
            "/a/test_domain/api/v0.5/form/",
            data={'_search': json.dumps(query)}
        )
        expected = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "term": {
                                "domain.exact": "test_domain"
                            }
                        },
                        {
                            "term": {
                                "doc_type": "xforminstance"
                            }
                        },
                        {
                            "bool": {
                                "should": [
                                    {
                                        "bool": {
                                            "filter": [
                                                {
                                                    "bool": {
                                                        "must_not": {
                                                            "bool": {
                                                                "must_not": {
                                                                    "exists": {
                                                                        "field": "server_modified_on"
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                },
                                                {
                                                    "range": {
                                                        "server_modified_on": {
                                                            "gte": "2019-01-01T00:00:00",
                                                            "lte": "2019-01-02T00:00:00"
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    },
                                    {
                                        "bool": {
                                            "filter": [
                                                {
                                                    "bool": {
                                                        "must_not": {
                                                            "exists": {
                                                                "field": "server_modified_on"
                                                            }
                                                        }
                                                    }
                                                },
                                                {
                                                    "range": {
                                                        "received_on": {
                                                            "gte": "2019-01-01T00:00:00",
                                                            "lte": "2019-01-02T00:00:00"
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    }
                                ]
                            }
                        },
                        {
                            "match_all": {}
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "size": 1000000
        }
        self.checkQuery(
            es_query_from_get_params(request.GET, 'test_domain'),
            expected,
            is_raw_query=True
        )

    def test_inserted_at_query(self):
        # GET param _search can accept a custom query from a custom API use case
        query = {
            'filter': {
                'range': {
                    'inserted_at': {'gt': '2020-06-27T20:51:23.773000'}
                }
            }
        }
        request = RequestFactory().get(
            "/a/test_domain/api/v0.5/form/",
            data={'_search': json.dumps(query)}
        )
        expected = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "term": {
                                "domain.exact": "test_domain"
                            }
                        },
                        {
                            "term": {
                                "doc_type": "xforminstance"
                            }
                        },
                        query['filter'],
                        {
                            "match_all": {}
                        }
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "size": 1000000
        }
        self.checkQuery(
            es_query_from_get_params(request.GET, 'test_domain'),
            expected,
            is_raw_query=True
        )

    def test_other_queries_get_skipped(self):
        # GET param _search shouldn't accept any other queries
        query = {
            'filter': {
                'range': {
                    'received_on': {'gt': '2020-06-27T20:51:23.773000'}
                }
            }
        }
        request = RequestFactory().get(
            "/a/test_domain/api/v0.5/form/",
            data={'_search': json.dumps(query)}
        )
        with self.assertRaises(Http400):
            es_query_from_get_params(request.GET, 'test_domain')


class TestApiThrottle(APIResourceTest):
    resource = v0_5.WebUserResource
    api_name = 'v0.5'
    patch = flag_disabled('API_THROTTLE_WHITELIST')

    def setUp(self):
        super().setUp()
        self.endpoint = "%s?%s" % (self.single_endpoint(self.user._id), urlencode({
            "username": self.user.username,
            "api_key": self.api_key.key
        }))

    def test_throttle_allowlist(self):
        """Test that the allowlist toggle allows all traffic through
        """
        with patch('corehq.apps.api.resources.meta.api_rate_limiter.allow_usage') as allow_access:
            allow_access.return_value = False

            response = self.client.get(self.endpoint)
            self.assertEqual(response.status_code, 429)

            with patch('corehq.apps.api.resources.meta.API_THROTTLE_WHITELIST.enabled') as toggle_patch:
                toggle_patch.return_value = True

                response = self.client.get(self.endpoint)

                self.assertEqual(response.status_code, 200)

    def test_should_be_throttled_identifier(self):
        """Test that the correct identifier is used for the throttle
        """
        with patch('corehq.apps.api.resources.meta.HQThrottle.should_be_throttled') as hq_should_be_throttled:

            self.client.get(self.endpoint)
            hq_should_be_throttled.assert_called_with(
                ApiIdentifier(domain=self.domain.name, username=self.user.username))

            with patch('corehq.apps.api.resources.meta.API_THROTTLE_WHITELIST.enabled') as toggle_patch:
                toggle_patch.return_value = True

                self.client.get(self.endpoint)

                hq_should_be_throttled.assert_called_with(
                    ApiIdentifier(domain=self.domain.name, username=self.user.username))


class TestUrls(APIResourceTest):
    resource = v0_5.CommCareUserResource
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        commcare_user = CommCareUser.create(domain=cls.domain.name, username='fake_user', password='*****',
                                            created_by=None, created_via=None)
        cls.addClassCleanup(commcare_user.delete, cls.domain.name, deleted_by=None)
        cls.user_id = commcare_user.user_id

    def test_v0_5(self):
        url = reverse('api_dispatch_detail', kwargs={
            'resource_name': 'user',
            'domain': self.domain.name,
            'api_name': 'v0.5',
            'pk': self.user_id,
        })
        self.assertEqual(url, f'/a/qwerty/api/v0.5/user/{self.user_id}/')
        response = self._assert_auth_get_resource(url)
        self.assertEqual(response.json()['resource_uri'],
                         f'/a/qwerty/api/v0.5/user/{self.user_id}/')

    def test_v1(self):
        url = reverse('api_dispatch_detail', kwargs={
            'resource_name': 'user',
            'domain': self.domain.name,
            'api_name': 'v1',
            'pk': self.user_id,
        })
        self.assertEqual(url, f'/a/qwerty/api/user/v1/{self.user_id}/')
        response = self._assert_auth_get_resource(url)
        self.assertEqual(response.json()['resource_uri'],
                         f'/a/qwerty/api/user/v1/{self.user_id}/')

    def test_user_scoped_api(self):
        for version, expected_url in [
                ('v0.5', '/api/v0.5/identity/'),
                ('v1', '/api/identity/v1/'),
        ]:
            url = reverse('api_dispatch_list', kwargs={
                'resource_name': 'identity',
                'api_name': version,
            })
            self.assertEqual(url, expected_url)
            self.assertEqual(self._assert_auth_get_resource(url).status_code, 200)
