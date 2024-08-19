from django.test import TestCase

from corehq.apps.accounting.models import Subscription, SubscriptionAdjustment
from corehq.apps.domain.models import Domain
from corehq.apps.sso.models import (
    IdentityProvider,
    AuthenticatedEmailDomain,
    TrustedIdentityProvider,
)
from corehq.apps.sso.tests import generator


class TestCacheCleanup(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = generator.get_billing_account_for_idp()
        cls.idp = IdentityProvider.objects.create(
            owner=cls.account,
            name='Entra ID for Vault Wax',
            slug='vaultwax',
            created_by='someadmin@dimagi.com',
            last_modified_by='someadmin@dimagi.com',
            is_active=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.idp.delete()
        cls.account.delete()
        super().tearDownClass()

    def _cleanup_identity_provider(self):
        self.idp.is_active = True
        self.idp.save()

    def test_cache_cleanup_when_email_domain_is_added_and_removed(self):
        """
        Ensure that the cache for
        IdentityProvider.get_active_identity_provider_by_email_domain
        is cleared  when an AuthenticatedEmailDomain is added or removed.
        """
        self.assertIsNone(
            IdentityProvider.get_active_identity_provider_by_email_domain('vaultwax.com')
        )
        email_domain = AuthenticatedEmailDomain.objects.create(
            email_domain='vaultwax.com',
            identity_provider=self.idp
        )
        self.assertEqual(
            IdentityProvider.get_active_identity_provider_by_email_domain('vaultwax.com'),
            self.idp
        )
        email_domain.delete()
        self.assertIsNone(
            IdentityProvider.get_active_identity_provider_by_email_domain('vaultwax.com')
        )

    def test_cache_cleanup_when_identity_provider_is_active_status_changes(self):
        """
        Ensure that the cache for
        IdentityProvider.get_active_identity_provider_by_email_domain
        is cleared when the IdentityProvider's is_active status changes from
        True to False.
        """
        self.addCleanup(self._cleanup_identity_provider)
        AuthenticatedEmailDomain.objects.create(
            email_domain='vaultwax.com',
            identity_provider=self.idp
        )
        self.assertEqual(
            IdentityProvider.get_active_identity_provider_by_email_domain('vaultwax.com'),
            self.idp
        )
        self.idp.is_active = False
        self.idp.save()
        self.assertIsNone(
            IdentityProvider.get_active_identity_provider_by_email_domain('vaultwax.com')
        )

    def test_cache_cleanup_when_idp_trust_relationship_changes(self):
        """
        Ensure that the cache for IdentityProvider.does_domain_trust_this_idp
        is cleared when a TrustedIdentityProvider is created or deleted.
        """
        self.assertFalse(
            self.idp.does_domain_trust_this_idp('vwx-001')
        )
        trust = TrustedIdentityProvider.objects.create(
            domain='vwx-001',
            identity_provider=self.idp,
            acknowledged_by='test@dimagi.com',
        )
        self.assertTrue(
            self.idp.does_domain_trust_this_idp('vwx-001')
        )
        trust.delete()
        self.assertFalse(
            self.idp.does_domain_trust_this_idp('vwx-001')
        )

    def test_cache_cleanup_when_domain_subscription_changes(self):
        """
        Ensure that the cache for IdentityProvider.does_domain_trust_this_idp
        is cleared when the status of a domain's subscription changes.
        """
        domain = Domain.get_or_create_with_name(
            "vaultwax-001",
            is_active=True
        )
        self.addCleanup(lambda: domain.delete())
        enterprise_plan = generator.get_enterprise_plan()

        self.assertFalse(self.idp.does_domain_trust_this_idp(domain.name))

        sub = Subscription.new_domain_subscription(
            self.idp.owner,
            domain.name,
            enterprise_plan,
        )
        self.assertTrue(self.idp.does_domain_trust_this_idp(domain.name))

        sub.is_active = False
        sub.save()
        self.assertFalse(self.idp.does_domain_trust_this_idp(domain.name))

        sub.is_active = True
        sub.save()
        self.assertTrue(self.idp.does_domain_trust_this_idp(domain.name))

        SubscriptionAdjustment.objects.all().delete()
        Subscription.visible_and_suppressed_objects.all().delete()
        self.assertFalse(self.idp.does_domain_trust_this_idp(domain.name))
