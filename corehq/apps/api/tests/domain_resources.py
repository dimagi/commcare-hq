import json
import uuid

import mock
from django.http import QueryDict
from django.test import RequestFactory

from corehq.apps.api.resources import v0_5
from corehq.apps.api.resources.v0_5 import UserInfo, CaseType, UserDomain
from corehq.apps.api.tests.utils import APIResourceTest, BundleMock
from corehq.apps.app_manager.models import Application
from corehq.util import reverse
from corehq.util.test_utils import create_and_save_a_case


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
        self.assertCountEqual(expected, actual)
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
