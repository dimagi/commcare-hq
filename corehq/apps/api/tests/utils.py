from __future__ import absolute_import, unicode_literals

from collections import OrderedDict

from django.test import TestCase
from django.urls import reverse
from django.utils.http import urlencode

import six
from django_prbac.models import Role
from tastypie.models import ApiKey

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.api.util import object_does_not_exist
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import PatchMeta, flag_enabled


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


class APIResourceTest(six.with_metaclass(PatchMeta, TestCase)):
    """
    Base class for shared API tests. Sets up a domain and user and provides
    some helper methods and properties for accessing the API
    """
    patch = flag_enabled('API_THROTTLE_WHITELIST')

    resource = None  # must be set by subclasses
    api_name = 'v0.4'  # can be overridden by subclasses
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

        for domain in Domain.get_all():
            Subscription._get_active_subscription_by_domain.clear(Subscription, domain.name)
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

    def _assert_auth_get_resource(self, url, username=None, password=None, failure_code=401, headers=None):
        """
        This tests that the given URL fails when accessed via sessions and returns the response
        obtained via using API auth. It's callers' responsibility to test resource specific logic
        using response returned.

        The user authentication is attempted via default self.username creds, other creds can be passed
        via username and password kwargs
        """
        username = username or self.username
        password = password or self.password
        headers = headers or {}

        # session based auth should fail
        self.client.login(username=username, password=password)
        response = self.client.get(url, **headers)
        self.assertEqual(response.status_code, failure_code)

        # api_key auth should succeed, caller can check for expected code
        api_url = self._api_url(url, username)
        response = self.client.get(api_url, **headers)
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
        elif method == "DELETE":
            response = self.client.delete(url, post_data, content_type=content_type)
        self.assertEqual(response.status_code, failure_code)

        # api_key auth should succeed, caller should check expected response status and content
        api_url = self._api_url(url)
        if method == "POST":
            response = self.client.post(api_url, post_data, content_type=content_type)
        elif method == "PUT":
            response = self.client.put(api_url, post_data, content_type=content_type)
        elif method == "DELETE":
            response = self.client.delete(api_url, post_data, content_type=content_type)
        return response
