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
        cls.addClassCleanup(cls.account.delete)
        cls.domain = Domain.get_or_create_with_name("vaultwax-001", is_active=True)
        cls.addClassCleanup(cls.domain.delete)

        # this will be the user that's "logging in" with SAML2 via the SsoBackend
        cls.user = WebUser.create(
            cls.domain.name, 'b@vaultwax.com', 'testpwd', None, None
        )
        cls.addClassCleanup(cls.user.delete, cls.domain.name, deleted_by=None)
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
        super().tearDownClass()

    def authenticate(self, request, **kw):
        def delete(user):
            if user is not None and user.username != self.user.username:
                if not isinstance(user, WebUser):
                    user = WebUser.get_by_username(user.username)
                user.delete(self.domain.name, deleted_by=None)

        user = auth.authenticate(request, **kw)
        self.addCleanup(delete, user)
        return user

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get('/sso/test')
        create_request_session(self.request, use_saml_sso=True)

    @staticmethod
    def _get_oidc_request():
        request = RequestFactory().get('/sso/oidc')
        create_request_session(request, use_oidc_sso=True)
        return request

    def test_backend_failure_without_username(self):
        """
        SsoBackend (and every backend) should fail because username was not
        passed to authenticate()
        """
        with self.assertRaises(KeyError):
            self.authenticate(
                request=self.request,
                idp_slug=self.idp.slug,
                is_handshake_successful=True,
            )

    def test_backend_failure_without_idp_slug(self):
        """
        SsoBackend should fail to move past the first check because an idp_slug
         was not passed to authenticate()
        """
        user = self.authenticate(
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
        user = self.authenticate(
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
        user = self.authenticate(
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
        user = self.authenticate(
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
        user = self.authenticate(
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
        user = self.authenticate(
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
        user = self.authenticate(
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
        user = self.authenticate(
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

    def test_new_user_displayname_is_used_if_first_and_last_are_missing(self):
        """
        Entra ID does not mark the First and Last names as required, only the
        Display Name. If First and Last are missing, ensure that this
        information is then obtained from the Display Name
        """
        username = 'v@vaultwax.com'
        reg_form = RegisterWebUserForm()
        reg_form.cleaned_data = {
            'email': username,
            'phone_number': '+15555555555',
            'project_name': 'test-vault',
            'persona': 'Other',
            'persona_other': "for tests",

        }
        generator.store_display_name_in_saml_user_data(
            self.request,
            'Vanessa van Beek'
        )
        AsyncSignupRequest.create_from_registration_form(reg_form)
        user = self.authenticate(
            request=self.request,
            username=username,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, username)
        self.assertEqual(user.first_name, 'Vanessa')
        self.assertEqual(user.last_name, 'van Beek')
        self.assertEqual(
            self.request.sso_new_user_messages['success'],
            [
                "User account for v@vaultwax.com created."
            ]
        )

    def test_new_user_displayname_with_one_name_is_used_as_first_name(self):
        """
        Ensure that if the Entra ID "Display Name" has only one name/word in
        it that only the first name is populated.
        """
        username = 'test@vaultwax.com'
        reg_form = RegisterWebUserForm()
        reg_form.cleaned_data = {
            'email': username,
            'phone_number': '+15555555555',
            'project_name': 'test-vault',
            'persona': 'Other',
            'persona_other': "for tests",

        }
        generator.store_display_name_in_saml_user_data(
            self.request,
            'Test'
        )
        AsyncSignupRequest.create_from_registration_form(reg_form)
        user = self.authenticate(
            request=self.request,
            username=username,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, username)
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, '')
        self.assertEqual(
            self.request.sso_new_user_messages['success'],
            [
                "User account for test@vaultwax.com created."
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
        user = self.authenticate(
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
        user = self.authenticate(
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
        user = self.authenticate(
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

    def test_new_user_is_populated_with_oidc_full_name_data(self):
        """
        Ensure that if the request is an oidc request, the first name and last name are obtained from the stored
        oidcUserData
        """
        request = self._get_oidc_request()
        username = 'liam@vaultwax.com'
        generator.store_full_name_in_oidc_user_data(
            request,
            'Liam',
            'Bakker'
        )
        user = self.authenticate(
            request=request,
            username=username,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, username)
        self.assertEqual(user.first_name, 'Liam')
        self.assertEqual(user.last_name, 'Bakker')
        self.assertEqual(
            request.sso_new_user_messages['success'],
            [
                f'User account for {username} created.',
            ]
        )

    def test_new_user_is_populated_with_oidc_display_name_data(self):
        """
        Ensure that if the request is an oidc request, the first name and last name are obtained from the stored
        display name oidcUserData
        """
        request = self._get_oidc_request()
        username = 'nile@vaultwax.com'
        generator.store_display_name_in_oidc_user_data(
            request,
            'Nile Jansen'
        )
        user = self.authenticate(
            request=request,
            username=username,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, username)
        self.assertEqual(user.first_name, 'Nile')
        self.assertEqual(user.last_name, 'Jansen')
        self.assertEqual(
            request.sso_new_user_messages['success'],
            [
                f'User account for {username} created.',
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
        user = self.authenticate(
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

    def test_new_user_with_capitals_in_username(self):
        """
        It is possible for the Identity Provider to supply a username with
        uppercase characters in it, which we do not support. If the username
        is not made lowercase, a BadValueError and a User.DoesNotExist error
        will be thrown during the user creation process. This test ensures
        that we process the username correctly.
        """
        username = 'Hello.World.313@vaultwax.com'
        generator.store_full_name_in_saml_user_data(
            self.request,
            'Hello',
            'World'
        )
        user = self.authenticate(
            request=self.request,
            username=username,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, username.lower())
        self.assertEqual(user.first_name, 'Hello')
        self.assertEqual(user.last_name, 'World')
        self.assertEqual(
            self.request.sso_new_user_messages['success'],
            [
                f'User account for {username.lower()} created.',
            ]
        )

    def test_successful_login(self):
        """
        This test demonstrates the requirements necessary for a SsoBackend to
        successfully return a user and report no login error.
        """
        user = self.authenticate(
            request=self.request,
            username=self.user.username,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, self.user.username)
        self.assertIsNone(self.request.sso_login_error)

    def test_deactivated_user_is_reactivated_after_successful_sso_login(self):
        web_user_to_be_reactivated = self._create_a_new_user_then_deactivate_user()

        django_user = auth.authenticate(
            request=self.request,
            username=web_user_to_be_reactivated.username,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )

        # refetch the WebUser object
        web_user = WebUser.get_by_username(web_user_to_be_reactivated.username)
        self.assertTrue(web_user.is_active)
        django_user.refresh_from_db()
        self.assertTrue(django_user.is_active)
        self.assertEqual(
            self.request.sso_new_user_messages['success'],
            [
                f'User account for {web_user.username} has been re-activated.',
            ]
        )

    def test_deactivated_user_is_reactivated_and_invitation_accepted(self):
        web_user_to_be_reactivated = self._create_a_new_user_then_deactivate_user()
        admin_role = StaticRole.domain_admin(self.domain.name)
        invitation = Invitation(
            domain=self.domain.name,
            email=web_user_to_be_reactivated.username,
            invited_by=self.user.couch_id,
            invited_on=datetime.datetime.utcnow(),
            role=admin_role.get_qualified_id(),
        )
        invitation.save()
        AsyncSignupRequest.create_from_invitation(invitation)
        django_user = auth.authenticate(
            request=self.request,
            username=invitation.email,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )

        # refetch the WebUser object
        web_user = WebUser.get_by_username(web_user_to_be_reactivated.username)
        self.assertTrue(web_user.is_active)
        django_user.refresh_from_db()
        self.assertTrue(django_user.is_active)
        self.assertEqual(
            self.request.sso_new_user_messages['success'],
            [
                f'User account for {invitation.email} has been re-activated.',
                f'You have been added to the "{invitation.domain}" project space.',
            ]
        )

    def test_deactivated_user_is_reactivated_and_expired_invitation_declined(self):
        web_user_to_be_reactivated = self._create_a_new_user_then_deactivate_user()
        invitation = Invitation(
            domain=self.domain.name,
            email=web_user_to_be_reactivated.username,
            invited_by=self.user.couch_id,
            invited_on=datetime.datetime.utcnow() - relativedelta(months=2),
        )
        invitation.save()
        AsyncSignupRequest.create_from_invitation(invitation)

        django_user = auth.authenticate(
            request=self.request,
            username=invitation.email,
            idp_slug=self.idp.slug,
            is_handshake_successful=True,
        )

        # refetch the WebUser object
        web_user = WebUser.get_by_username(web_user_to_be_reactivated.username)
        self.assertTrue(web_user.is_active)
        django_user.refresh_from_db()
        self.assertTrue(django_user.is_active)
        self.assertEqual(
            self.request.sso_new_user_messages['success'],
            [
                f'User account for {invitation.email} has been re-activated.',
            ]
        )
        self.assertEqual(
            self.request.sso_new_user_messages['error'],
            [
                'Could not accept invitation because it is expired.',
            ]
        )

    def test_failed_sso_login_does_not_reactivate_user(self):
        """
        This test ensures that a failed SSO login attempt does not reactivate a deactivated user.
        """
        deactivated_user = self._create_a_new_user_then_deactivate_user()

        # When SSO authentication fails
        user = auth.authenticate(
            request=self.request,
            username=deactivated_user.username,
            idp_slug=self.idp.slug,
            is_handshake_successful=False,  # Simulate a failed handshake/authentication
        )

        # refetch the WebUser object
        web_user = WebUser.get_by_username(deactivated_user.username)
        self.assertFalse(web_user.is_active)
        self.assertIsNone(user)

    def _create_a_new_user_then_deactivate_user(self):
        user = WebUser.create(
            None, 'reactivate@vaultwax.com', 'testpwd', None, None
        )
        user.is_active = False
        user.save()
        self.addCleanup(user.delete, None, deleted_by=None)
        return user
