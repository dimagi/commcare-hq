from datetime import datetime, timezone
from unittest.mock import patch

from django.http import Http404
from django.test import RequestFactory, TestCase

from tastypie.exceptions import ImmediateHttpResponse

from corehq.apps.accounting.models import (
    DefaultProductPlan,
    SoftwarePlanEdition,
)
from corehq.apps.accounting.tests.utils import generator
from corehq.apps.domain.models import Domain
from corehq.apps.enterprise.api.resources import (
    EnterpriseODataAuthentication,
    ODataAuthentication,
)
from corehq.apps.users.models import WebUser


class EnterpriseODataAuthenticationTests(TestCase):
    def setUp(self):
        super().setUp()
        patcher = patch.object(ODataAuthentication, 'is_authenticated', return_value=True)
        self.mock_is_authentication = patcher.start()
        self.addCleanup(patcher.stop)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls._create_user('admin@testing-domain.com')
        cls.account = cls._create_enterprise_account_covering_domains(['testing-domain'])
        cls.account.enterprise_admin_emails = [cls.user.username]
        cls.account.save()

    def test_successful_authentication(self):
        request = self._create_request(self.user, 'testing-domain')

        auth = EnterpriseODataAuthentication()
        self.assertTrue(auth.is_authenticated(request))

    def test_parent_failure_returns_parent_results(self):
        self.mock_is_authentication.return_value = False

        request = self._create_request(self.user, 'testing-domain')

        auth = EnterpriseODataAuthentication()
        self.assertFalse(auth.is_authenticated(request))

    def test_raises_exception_when_billing_account_does_not_exist(self):
        request = self._create_request(self.user, 'not-testing-domain')

        auth = EnterpriseODataAuthentication()
        with self.assertRaises(Http404):
            auth.is_authenticated(request)

    def test_raises_exception_when_not_an_enterprise_admin(self):
        self.account.enterprise_admin_emails = ['not-this-user@testing-domain.com']
        self.account.save()

        request = self._create_request(self.user, 'testing-domain')

        auth = EnterpriseODataAuthentication()
        with self.assertRaises(ImmediateHttpResponse):
            auth.is_authenticated(request)

    @classmethod
    def _create_enterprise_account_covering_domains(cls, domains):
        billing_account = generator.billing_account(
            'test-admin@dimagi.com',
            'test-admin@dimagi.com',
            is_customer_account=True
        )

        enterprise_plan = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.ENTERPRISE)

        for domain in domains:
            domain_obj = Domain(name=domain, is_active=True)
            domain_obj.save()
            cls.addClassCleanup(domain_obj.delete)

            generator.generate_domain_subscription(
                billing_account,
                domain_obj,
                datetime.now(timezone.utc),
                None,
                plan_version=enterprise_plan,
                is_active=True
            )

        return billing_account

    @classmethod
    def _create_user(cls, username):
        return WebUser(username=username)

    def _create_request(self, user, domain):
        request = RequestFactory().get('/')
        request.couch_user = user
        request.domain = domain
        return request
