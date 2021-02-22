from django.contrib import auth
from django.test import TestCase, RequestFactory

from corehq.apps.domain.models import Domain
from corehq.apps.sso.models import IdentityProvider, AuthenticatedEmailDomain
from corehq.apps.sso.tests import generator
from corehq.apps.users.models import WebUser


class TestSsoBackend(TestCase):
    """
    This ensures that authentication through the SsoBackend only succeeds
    when a samlSessionIndex is present and the Identity Provider, its
    associated email domains, and the username all meet required criteria.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = generator.get_billing_account_for_idp()
        cls.domain = Domain(
            name="vaultwax-001",
            is_active=True
        )
        cls.domain.save()

        # this will be the user that's "logging in" with SAML2 via the SsoBackend
        cls.user = WebUser.create(
            cls.domain.name, 'b@vaultwax.com', 'testpwd', None, None
        )
        cls.idp = generator.create_idp('vaultwax', cls.account)
        cls.idp_two = generator.create_idp('vwx-link', cls.account)

    @classmethod
    def tearDownClass(cls):
        IdentityProvider.objects.all().delete()
        cls.user.delete(None)
        cls.domain.delete()
        cls.account.delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        # Identity Provider is_active is always True by default for each test
        self.idp.is_active = True
        self.idp.save()

        self.request = RequestFactory().get('/sso/test')
        self.request.session = {}

    def tearDown(self):
        AuthenticatedEmailDomain.objects.all().delete()
        super().tearDown()

    def _set_saml_session_index(self):
        self.request.session['samlSessionIndex'] = '_7c84c96e-8774-4e64-893c-06f91d285100'

    def test_backend_failure_without_idp_slug(self):
        """
        SsoBackend should fail to move past the first check because an idp_slug
         was not passed to authenticate()
        """
        self._set_saml_session_index()
        user = auth.authenticate(
            request=self.request,
            username=self.user.username
        )
        self.assertIsNone(user)
        with self.assertRaises(AttributeError):
            self.request.sso_login_error

    def test_backend_failure_without_saml_session_index(self):
        """
        SsoBackend should fail to move past the first check because a
         samlSessionIndex is not present in request.session.
        """
        user = auth.authenticate(
            request=self.request,
            username=self.user.username,
            idp_slug=self.idp.slug
        )
        self.assertIsNone(user)

    def test_login_error_if_idp_doesnt_exist(self):
        """
        SsoBackend should fail to return a user if the Identity Provider
        slug associated with that user does not exist. It should also populate
        request.sso_login_error with an error message.
        """
        self._set_saml_session_index()
        user = auth.authenticate(
            request=self.request,
            username=self.user.username,
            idp_slug='doesnotexist'
        )
        self.assertIsNone(user)
        self.assertEqual(
            self.request.sso_login_error,
            "Identity Provider does not exist."
        )

    def test_login_error_if_idp_not_active(self):
        """
        SsoBackend should fail to return a user if the Identity Provider
        associated with that user is not active. It should also populate
        request.sso_login_error with an error message.
        """
        self._set_saml_session_index()
        self.idp.is_active = False
        self.idp.save()
        user = auth.authenticate(
            request=self.request,
            username=self.user.username,
            idp_slug=self.idp.slug
        )
        self.assertIsNone(user)
        self.assertEqual(
            self.request.sso_login_error,
            "This Identity Provider is not active."
        )

    def test_login_error_if_bad_username(self):
        """
        SsoBackend should fail to return a user if the username passed to it
        is not a valid email address (missing email domain / no `@`). It should
        also populate request.sso_login_error with an error message.
        """
        self._set_saml_session_index()
        user = auth.authenticate(
            request=self.request,
            username='badusername',
            idp_slug=self.idp.slug
        )
        self.assertIsNone(user)
        self.assertEqual(
            self.request.sso_login_error,
            "Username badusername is not valid."
        )

    def test_login_error_if_email_domain_does_not_exist(self):
        """
        SsoBackend should fail to return a user if the username passed to it
        matches an email domain that is not mapped to any Identity Provider.
        It should also populate request.sso_login_error with an error message.
        """
        self._set_saml_session_index()
        user = auth.authenticate(
            request=self.request,
            username='b@vwx.link',
            idp_slug=self.idp.slug
        )
        self.assertIsNone(user)
        self.assertEqual(
            self.request.sso_login_error,
            "The Email Domain vwx.link is not allowed to authenticate with "
            "this Identity Provider."
        )

    def test_login_error_if_email_domain_is_not_authorized(self):
        """
        SsoBackend should fail to return a user if the username passed to it
        matches an email domain that exists, but is not authorized to
        authenticate with the Identity Provider in the request. It should also
        populate request.sso_login_error with an error message.
        """
        self._set_saml_session_index()
        AuthenticatedEmailDomain.objects.create(
            email_domain='vwx.link',
            identity_provider=self.idp_two,  # note that this is not self.idp
        )
        user = auth.authenticate(
            request=self.request,
            username='b@vwx.link',
            idp_slug=self.idp.slug  # note that this is self.idp, not idp_two
        )
        self.assertIsNone(user)
        self.assertEqual(
            self.request.sso_login_error,
            "The Email Domain vwx.link is not allowed to authenticate with "
            "this Identity Provider."
        )

    def test_login_error_if_user_does_not_exist(self):
        """
        SsoBackend should fail to return a user if the username passed to does
        not exist. It should also populate request.sso_login_error with an
        error message.

        todo this test will change with additional user creation workflows
         that will be introduced later
        """
        self._set_saml_session_index()
        AuthenticatedEmailDomain.objects.create(
            email_domain='vaultwax.com',
            identity_provider=self.idp,
        )
        user = auth.authenticate(
            request=self.request,
            username='testnoexist@vaultwax.com',
            idp_slug=self.idp.slug
        )
        self.assertIsNone(user)
        self.assertEqual(
            self.request.sso_login_error,
            "User testnoexist@vaultwax.com does not exist."
        )

    def test_successful_login(self):
        """
        This test demonstrates the requirements necessary for a SsoBackend to
        successfully return a user and report no login error.
        """
        self._set_saml_session_index()
        AuthenticatedEmailDomain.objects.create(
            email_domain='vaultwax.com',
            identity_provider=self.idp,
        )
        user = auth.authenticate(
            request=self.request,
            username=self.user.username,
            idp_slug=self.idp.slug
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, self.user.username)
        self.assertIsNone(self.request.sso_login_error)
