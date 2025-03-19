from django.test import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.sso.tests import generator
from corehq.apps.sso.models import (
    AuthenticatedEmailDomain,
    IdentityProvider,
    TrustedIdentityProvider,
)
from corehq.apps.accounting.models import Subscription
from corehq.apps.sso.utils.domain_helpers import is_domain_using_sso


class TestIsDomainUsingSso(TestCase):
    """
    These tests ensure that is_domain_using_sso returns the correct result
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        enterprise_plan = generator.get_enterprise_plan()

        cls.account = generator.get_billing_account_for_idp()
        cls.domain_with_sso = Domain.get_or_create_with_name(
            "helping-earth-001",
            is_active=True
        )
        Subscription.new_domain_subscription(
            account=cls.account,
            domain=cls.domain_with_sso.name,
            plan_version=enterprise_plan,
        )
        cls.idp = generator.create_idp('helping-earth', cls.account)
        cls.idp.is_active = True
        cls.idp.save()

        cls.account_pending_sso = generator.get_billing_account_for_idp()
        cls.domain_pending_sso = Domain.get_or_create_with_name(
            "dimagi-dot-org-001",
            is_active=True
        )
        Subscription.new_domain_subscription(
            account=cls.account_pending_sso,
            domain=cls.domain_pending_sso.name,
            plan_version=enterprise_plan,
        )

        cls.inactive_idp_account = generator.get_billing_account_for_idp()
        cls.domain_with_inactive_sso = Domain.get_or_create_with_name(
            "vaultwax-001",
            is_active=True
        )
        Subscription.new_domain_subscription(
            account=cls.inactive_idp_account,
            domain=cls.domain_with_inactive_sso.name,
            plan_version=enterprise_plan,
        )
        cls.inactive_idp = generator.create_idp('vaultwax', cls.inactive_idp_account)

        cls.domain_trusting_idp = Domain.get_or_create_with_name(
            "domain-trusts-helping-earth",
            is_active=True
        )
        cls.idp.create_trust_with_domain(
            cls.domain_trusting_idp.name,
            "test@helpingearth.org"
        )

        cls.domain_trusting_inactive_idp = Domain.get_or_create_with_name(
            "domain-trusts-vaultwax",
            is_active=True
        )
        cls.inactive_idp.create_trust_with_domain(
            cls.domain_trusting_inactive_idp.name,
            "test@vaultwax.com"
        )

        cls.other_domain = Domain.get_or_create_with_name(
            "hello-test",
            is_active=True
        )

    @classmethod
    def tearDownClass(cls):
        AuthenticatedEmailDomain.objects.all().delete()
        TrustedIdentityProvider.objects.all().delete()
        IdentityProvider.objects.all().delete()
        cls.domain_with_sso.delete()
        cls.domain_pending_sso.delete()
        cls.domain_with_inactive_sso.delete()
        cls.domain_trusting_idp.delete()
        cls.domain_trusting_inactive_idp.delete()
        cls.other_domain.delete()
        super().tearDownClass()

    def test_domain_under_active_idp_returns_true(self):
        """
        Ensure that domains which are members of a BillingAccount tied
        to an active Identity Provider return True on is_domain_using_sso
        """
        self.assertTrue(is_domain_using_sso(self.domain_with_sso.name))

    def test_domain_under_inactive_idp_returns_false(self):
        """
        Ensure that domains which are members of a BillingAccount tied
        to an inactive Identity Provider return False on is_domain_using_sso
        """
        self.assertFalse(is_domain_using_sso(self.domain_with_inactive_sso.name))

    def test_domain_trusting_active_idp_returns_true(self):
        """
        Ensure that a domain which trusts an active Identity Provider
        returns true
        """
        self.assertTrue(is_domain_using_sso(self.domain_trusting_idp.name))

    def test_domain_trusting_inactive_idp_returns_false(self):
        """
        Ensure that a domain which trusts an inactive Identity Provider
        returns false
        """
        self.assertFalse(is_domain_using_sso(self.domain_trusting_inactive_idp.name))

    def test_non_sso_domain_returns_false(self):
        """
        Ensure that a domain which is not tied to an active Identity Provider
        either by trusting one or through an account returns false
        """
        self.assertFalse(is_domain_using_sso(self.other_domain.name))

    def test_cache_is_cleared_when_domain_is_added_to_idp(self):
        """
        Ensure that the quickcache for is_domain_using_sso properly gets
        cleared when a domain suddenly gains SSO access.
        """
        self.addCleanup(is_domain_using_sso.clear, self.domain_pending_sso.name)
        self.assertFalse(is_domain_using_sso(self.domain_pending_sso.name))
        new_idp = generator.create_idp('dimagi-org', self.account_pending_sso)
        new_idp.is_active = True
        new_idp.save()
        new_idp.save()  # this avoids a race condition with tests
        self.assertTrue(is_domain_using_sso(self.domain_pending_sso.name))
