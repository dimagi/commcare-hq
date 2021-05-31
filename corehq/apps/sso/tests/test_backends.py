import datetime

from dateutil.relativedelta import relativedelta
from django.contrib import auth
from django.test import TestCase, RequestFactory

from corehq.apps.domain.models import Domain
from corehq.apps.registration.forms import RegisterWebUserForm
from corehq.apps.registration.models import AsyncSignupRequest
from corehq.apps.sso.models import IdentityProvider, AuthenticatedEmailDomain
from corehq.apps.sso.tests import generator
from corehq.apps.sso.tests.generator import create_request_session
from corehq.apps.users.models import WebUser, Invitation, StaticRole


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
        cls.domain = Domain.get_or_create_with_name("vaultwax-001", is_active=True)

        # this will be the user that's "logging in" with SAML2 via the SsoBackend
        cls.user = WebUser.create(
            cls.domain.name, 'b@vaultwax.com', 'testpwd', None, None
        )
        cls.idp = generator.create_idp('vaultwax', cls.account)
        cls.idp.is_active = True
        cls.idp.save()
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
        cls.user.delete(cls.domain.name, deleted_by=None)

        # cleanup "new" users
        for username in [
            'm@vaultwax.com',
            'isa@vaultwax.com',
            'zee@vaultwax.com',
            'exist@vaultwax.com',
            'aart@vaultwax.com',
        ]:
            web_user = WebUser.get_by_username(username)
            if web_user:
                web_user.delete(cls.domain.name, deleted_by=None)

        cls.domain.delete()
        cls.account.delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get('/sso/test')
        create_request_session(self.request)

    def test_backend_failure_without_username(self):
        """
        SsoBackend (and every backend) should fail because username was not
        passed to authenticate()
        """
        with self.assertRaises(KeyError):
            auth.authenticate(
                request=self.request,
                idp_slug=self.idp.slug,
                is_handshake_successful=True,
            )

    def test_backend_failure_without_idp_slug(self):
        """
        SsoBackend should fail to move past the first check because an idp_slug
         was not passed to authenticate()
        """
        user = auth.authenticate(
            request=self.request,
            username=self.user.username,
            is_handshake_successful=True,
        )
        self.assertIsNone(user)
        with self.assertRaises(AttributeError):
            self.request.sso_login_error

    def test_backend_failure_without_is_handshake_successful_flag(self):
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
        with self.assertRaises(AttributeError):
            self.request.sso_login_error

    def test_login_error_if_idp_doesnt_exist(self):
        """
        SsoBackend should fail to return a user if the Identity Provider
        slug associated with that user does not exist. It should also populate
        request.sso_login_error with an error message.
        """
        user = auth.authenticate(
            request=self.request,
            username=self.user.username,
            idp_slug='doesnotexist',
            is_handshake_successful=True,
        )
        self.assertIsNone(user)
        self.assertEqual(
            self.request.sso_login_error,
            "Identity Provider doesnotexist does not exist."
        )

    def _activate_idp(self):
        self.idp.is_active = True
        self.idp.save()

    def test_login_error_if_idp_not_active(self):
        """
        SsoBackend should fail to return a user if the Identity Provider
        associated with that user is not active. It should also populate
        request.sso_login_error with an error message.
        """
        self.addCleanup(self._activate_idp)
        self.idp.is_active = False
        self.idp.save()
        user = auth.authenticate(
            request=self.request,
            username=self.user.username,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNone(user)
        self.assertEqual(
            self.request.sso_login_error,
            "This Identity Provider vaultwax is not active."
        )

    def test_login_error_if_bad_username(self):
        """
        SsoBackend should fail to return a user if the username passed to it
        is not a valid email address (missing email domain / no `@`). It should
        also populate request.sso_login_error with an error message.
        """
        user = auth.authenticate(
            request=self.request,
            username='badusername',
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
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
        user = auth.authenticate(
            request=self.request,
            username='b@idonotexist.com',
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNone(user)
        self.assertEqual(
            self.request.sso_login_error,
            "The Email Domain idonotexist.com is not allowed to authenticate "
            "with this Identity Provider (vaultwax)."
        )

    def test_login_error_if_email_domain_is_not_authorized(self):
        """
        SsoBackend should fail to return a user if the username passed to it
        matches an email domain that exists, but is not authorized to
        authenticate with the Identity Provider in the request. It should also
        populate request.sso_login_error with an error message.
        """
        user = auth.authenticate(
            request=self.request,
            username='b@vwx.link',
            idp_slug=self.idp.slug,  # note that this is self.idp, not idp_vwx
            is_handshake_successful=True,
        )
        self.assertIsNone(user)
        self.assertEqual(
            self.request.sso_login_error,
            "The Email Domain vwx.link is not allowed to authenticate with "
            "this Identity Provider (vaultwax)."
        )

    def test_new_user_created_and_data_is_saved(self):
        """
        SsoBackend should create a new user if the username passed to does
        not exist and the email domain matches an AuthenticatedEmailDomain
        for the given IdentityProvider. It should also ensure that any
        user data from a registration form and/or the samlUserdata are all
        properly saved to the User model.
        """
        username = 'm@vaultwax.com'
        reg_form = RegisterWebUserForm()
        reg_form.cleaned_data = {
            'email': username,
            'phone_number': '+15555555555',
            'project_name': 'test-vault',
            'persona': 'Other',
            'persona_other': "for tests",

        }
        generator.store_full_name_in_saml_user_data(
            self.request,
            'Maarten',
            'van der Berg'
        )
        AsyncSignupRequest.create_from_registration_form(reg_form)
        user = auth.authenticate(
            request=self.request,
            username=username,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, username)
        self.assertEqual(user.first_name, 'Maarten')
        self.assertEqual(user.last_name, 'van der Berg')
        web_user = WebUser.get_by_username(user.username)
        self.assertEqual(web_user.phone_numbers[0], '+15555555555')
        self.assertEqual(
            self.request.sso_new_user_messages['success'],
            [
                "User account for m@vaultwax.com created."
            ]
        )

    def test_new_user_created_and_invitation_accepted(self):
        """
        When SsoBackend creates a new user and an invitation is present, that
        invitation should add the user to the invited project
        space and accept the invitation
        """
        admin_role = StaticRole.domain_admin(self.domain.name)
        invitation = Invitation(
            domain=self.domain.name,
            email='isa@vaultwax.com',
            invited_by=self.user.couch_id,
            invited_on=datetime.datetime.utcnow(),
            role=admin_role.get_qualified_id(),
        )
        invitation.save()
        AsyncSignupRequest.create_from_invitation(invitation)
        generator.store_full_name_in_saml_user_data(
            self.request,
            'Isa',
            'Baas'
        )
        user = auth.authenticate(
            request=self.request,
            username=invitation.email,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, invitation.email)
        self.assertEqual(user.first_name, 'Isa')
        self.assertEqual(user.last_name, 'Baas')
        self.assertEqual(
            self.request.sso_new_user_messages['success'],
            [
                f'User account for {invitation.email} created.',
                f'You have been added to the "{invitation.domain}" project space.',
            ]
        )

    def test_new_user_created_and_expired_invitation_declined(self):
        """
        When SsoBackend creates a new user and an EXPIRED invitation is present,
        a new user should still be created, but the invitation should be declined.
        """
        invitation = Invitation(
            domain=self.domain.name,
            email='zee@vaultwax.com',
            invited_by=self.user.couch_id,
            invited_on=datetime.datetime.utcnow() - relativedelta(months=2),
        )
        invitation.save()
        AsyncSignupRequest.create_from_invitation(invitation)
        generator.store_full_name_in_saml_user_data(
            self.request,
            'Zee',
            'Bos'
        )
        user = auth.authenticate(
            request=self.request,
            username=invitation.email,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, invitation.email)
        self.assertEqual(user.first_name, 'Zee')
        self.assertEqual(user.last_name, 'Bos')
        self.assertEqual(
            self.request.sso_new_user_messages['success'],
            [
                f'User account for {invitation.email} created.',
            ]
        )
        self.assertEqual(
            self.request.sso_new_user_messages['error'],
            [
                'Could not accept invitation because it is expired.',
            ]
        )

    def test_existing_user_invitation_accepted(self):
        """
        SsoBackend should create a new user if the username passed to does
        not exist and the email domain matches an AuthenticatedEmailDomain
        for the given IdentityProvider. It should also ensure that any
        user data from a registration form and/or the samlUserdata are all
        properly saved to the User model.
        """
        admin_role = StaticRole.domain_admin(domain=self.domain.name)
        existing_user = WebUser.create(
            None, 'exist@vaultwax.com', 'testpwd', None, None
        )
        invitation = Invitation(
            domain=self.domain.name,
            email=existing_user.username,
            invited_by=self.user.couch_id,
            invited_on=datetime.datetime.utcnow(),
            role=admin_role.get_qualified_id(),
        )
        invitation.save()
        AsyncSignupRequest.create_from_invitation(invitation)
        user = auth.authenticate(
            request=self.request,
            username=invitation.email,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, invitation.email)
        self.assertEqual(
            self.request.sso_new_user_messages['success'],
            [
                f'You have been added to the "{invitation.domain}" project space.',
            ]
        )

    def test_new_user_with_no_async_signup_request_creates_new_user(self):
        """
        There is a use case where brand new users can click on the CommCare HQ
        App icon right from their Active Directory home screen. In this case,
        we want to create the user's account and then present them with any
        project invitations once they have logged in.
        """
        username = 'aart@vaultwax.com'
        generator.store_full_name_in_saml_user_data(
            self.request,
            'Aart',
            'Janssen'
        )
        user = auth.authenticate(
            request=self.request,
            username=username,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, username)
        self.assertEqual(user.first_name, 'Aart')
        self.assertEqual(user.last_name, 'Janssen')
        self.assertEqual(
            self.request.sso_new_user_messages['success'],
            [
                f'User account for {username} created.',
            ]
        )

    def test_successful_login(self):
        """
        This test demonstrates the requirements necessary for a SsoBackend to
        successfully return a user and report no login error.
        """
        user = auth.authenticate(
            request=self.request,
            username=self.user.username,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, self.user.username)
        self.assertIsNone(self.request.sso_login_error)
