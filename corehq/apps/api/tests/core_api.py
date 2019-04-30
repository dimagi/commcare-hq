from __future__ import absolute_import, unicode_literals

from django.test import TestCase
from django.urls import reverse
from django.utils.http import urlencode

from six.moves import range
from tastypie import fields
from tastypie.models import ApiKey
from tastypie.resources import Resource

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.api.es import ElasticAPIQuerySet
from corehq.apps.api.fields import (
    ToManyDictField,
    ToManyDocumentsField,
    ToOneDocumentField,
    UseIfRequested,
)
from corehq.apps.api.resources import v0_4, v0_5
from corehq.apps.api.util import get_obj
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser, WebUser

from .utils import APIResourceTest, FakeXFormES


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
