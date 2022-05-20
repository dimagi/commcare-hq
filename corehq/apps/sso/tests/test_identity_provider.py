from django.test import TestCase

from corehq.apps.sso.models import LoginEnforcementType, AuthenticatedEmailDomain, IdentityProvider, SsoTestUser
from corehq.apps.sso.tests import generator


class TestIdentityProviderLoginEnforcements(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = generator.get_billing_account_for_idp()

    def setUp(self):
        super().setUp()
        self.idp = generator.create_idp('vaultwax', self.account)
        self.email_domain = AuthenticatedEmailDomain.objects.create(
            email_domain="vaultwax.com",
            identity_provider=self.idp,
        )

    def test_active_global_idp_is_required(self):
        self.idp.is_active = True
        self.idp.login_enforcement_type = LoginEnforcementType.GLOBAL
        self.idp.save()
        required_idp = IdentityProvider.get_required_identity_provider('b@vaultwax.com')
        self.assertEqual(required_idp, self.idp)

    def test_active_test_idp_is_required_with_test_user(self):
        self.idp.is_active = True
        self.idp.login_enforcement_type = LoginEnforcementType.TEST
        self.idp.save()
        test_user = SsoTestUser.objects.create(
            email_domain=self.email_domain,
            username='test@vaultwax.com',
        )

        # not required for non-test user
        required_idp = IdentityProvider.get_required_identity_provider('b@vaultwax.com')
        self.assertEqual(required_idp, None)

        required_idp = IdentityProvider.get_required_identity_provider(test_user.username)
        self.assertEqual(required_idp, self.idp)

    def test_inactive_idp_is_never_required(self):
        required_idp = IdentityProvider.get_required_identity_provider('b@vaultwax.com')
        self.assertEqual(required_idp, None)
