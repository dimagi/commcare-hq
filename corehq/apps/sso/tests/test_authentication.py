from django.test import TestCase, RequestFactory

from corehq.apps.domain.models import Domain
from corehq.apps.sso.authentication import get_authenticated_sso_user
from corehq.apps.sso.exceptions import SsoAuthenticationError
from corehq.apps.sso.models import IdentityProvider, AuthenticatedEmailDomain
from corehq.apps.sso.tests import generator
from corehq.apps.users.models import WebUser


class TestGetAuthenticatedSsoUser(TestCase):
    """
    This ensures that get_authenticated_sso_user succeeds only when the
    request has met all required criteria.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = generator.get_billing_account_for_idp()
        cls.domain = Domain.get_or_create_with_name("vaultwax-001", is_active=True)

        # this will be the user that's "logging in" with SAML2 via the SsoBackend
        cls.user = WebUser.create(
            cls.domain.name, 'b@vaultwax.com', 'testpwd', None, None
        )
        cls.idp = generator.create_idp('vaultwax', cls.account)
        AuthenticatedEmailDomain.objects.create(
            email_domain='vaultwax.com',
            identity_provider=cls.idp,
        )

        idp_vwx = generator.create_idp('vwx-link', cls.account)
        AuthenticatedEmailDomain.objects.create(
            email_domain='vwx.link',
            identity_provider=idp_vwx,  # note which idp is mapped here
        )

    @classmethod
    def tearDownClass(cls):
        AuthenticatedEmailDomain.objects.all().delete()
        IdentityProvider.objects.all().delete()
        cls.user.delete(None)
        cls.domain.delete()
        cls.account.delete()
        super().tearDownClass()

    def test_authentication_error_if_idp_doesnt_exist(self):
        """
        get_authenticated_sso_user should throw an SsoAuthenticationError if
        the Identity Provider slug passed to it points to a non-existent
        Identity Provider.
        """
        with self.assertRaises(SsoAuthenticationError):
            get_authenticated_sso_user(
                self.user.username,
                'doesnotexist'
            )

    def test_authentication_error_if_idp_not_active(self):
        """
        get_authenticated_sso_user should throw an SsoAuthenticationError if
        the specified Identity Provider is not active.
        """
        self.idp.is_active = False
        self.idp.save()
        with self.assertRaises(SsoAuthenticationError):
            get_authenticated_sso_user(
                self.user.username,
                self.idp.slug
            )

        self.idp.is_active = True
        self.idp.save()

    def test_authentication_error_if_bad_username(self):
        """
        get_authenticated_sso_user should throw an SsoAuthenticationError if
        the username passed to it is not a valid email address (missing email
        domain / no `@`).
        """
        with self.assertRaises(SsoAuthenticationError):
            get_authenticated_sso_user(
                'badusername',
                self.idp.slug
            )

    def test_authentication_error_if_email_domain_does_not_exist(self):
        """
        get_authenticated_sso_user should throw an SsoAuthenticationError if
        the username passed to it matches an email domain that is not mapped 
        to any Identity Provider.
        """
        with self.assertRaises(SsoAuthenticationError):
            get_authenticated_sso_user(
                'b@idonotexist.com',
                self.idp.slug
            )

    def test_authentication_error_if_email_domain_is_not_authorized(self):
        """
        get_authenticated_sso_user should throw an SsoAuthenticationError if
        the username passed to it matches an email domain that exists, but is
        not authorized to authenticate with the Identity Provider in the request.
        """
        with self.assertRaises(SsoAuthenticationError):
            get_authenticated_sso_user(
                'b@vwx.link',
                self.idp.slug  # note that this is self.idp, not idp_vwx
            )
    
    def test_authentication_error_if_user_does_not_exist(self):
        """
        get_authenticated_sso_user should throw an SsoAuthenticationError if
        the username passed to does not exist.

        todo this test will change with additional user creation workflows
         that will be introduced later
        """
        with self.assertRaises(SsoAuthenticationError):
            get_authenticated_sso_user(
                'testnoexist@vaultwax.com',
                self.idp.slug
            )
            
    def test_successful_authentication(self):
        """
        This test demonstrates the requirements necessary for
        get_authenticated_sso_user to successfully return a user.
        """
        user = get_authenticated_sso_user(
            self.user.username,
            self.idp.slug
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, self.user.username)
