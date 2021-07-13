from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory

from corehq.apps.accounting.models import Subscription
from corehq.apps.domain.models import Domain
from corehq.apps.registration.utils import request_new_domain
from corehq.apps.users.models import WebUser


class TestRequestNewDomain(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.new_user = WebUser.create(
            None, 'new@dimagi.org', 'testpwd', None, None
        )
        cls.request = RequestFactory().get('/registration')
        django_user = User.objects.get(username=cls.new_user.username)
        cls.request.user = django_user
        cls.domain_sso_test = 'test-sso-1'
        cls.domain_test = 'test-1'

    def tearDown(self):
        for domain in [self.domain_sso_test, self.domain_test]:
            Subscription._get_active_subscription_by_domain.clear(
                Subscription,
                domain
            )
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.new_user.delete(cls.domain_test, deleted_by=None)
        super().tearDownClass()

    def test_domain_is_active_for_new_sso_user(self):
        """
        Ensure that the first domain created by a new SSO user is active.
        """
        domain_name = request_new_domain(
            self.request,
            'test-sso-1',
            is_new_user=True,
            is_new_sso_user=True,
        )
        domain = Domain.get_by_name(domain_name)
        self.assertTrue(domain.is_active)

    def test_domain_is_not_active_for_new_user(self):
        """
        Ensure that the first domain created by a new user is not active.
        """
        domain_name = request_new_domain(
            self.request,
            'test-sso-2',
            is_new_user=True,
        )
        domain = Domain.get_by_name(domain_name)
        self.assertFalse(domain.is_active)
