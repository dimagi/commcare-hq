import json

from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.test import TestCase, override_settings
from django.urls import reverse

from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.forms import EmailAuthenticationForm
from corehq.apps.sso.models import (
    IdentityProvider,
    AuthenticatedEmailDomain,
    UserExemptFromSingleSignOn,
)
from corehq.apps.users.models import WebUser
from corehq.apps.sso.tests import generator


class TestHQLoginViewWithSso(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = generator.get_billing_account_for_idp()
        cls.domain = Domain.get_or_create_with_name(
            "helping-earth-001",
            is_active=True
        )
        cls.non_sso_domain = Domain.get_or_create_with_name(
            "my-project",
            is_active=True
        )
        cls.user_sso_exempt = WebUser.create(
            cls.domain.name, 'jorge@helpingearth.org', 'testpwd', None, None
        )
        cls.user_sso_required = WebUser.create(
            cls.domain.name, 'sara@helpingearth.org', 'testpwd', None, None
        )
        cls.user_no_sso = WebUser.create(
            cls.non_sso_domain.name, 'j@uni.edu', 'testpwd', None, None
        )
        cls.idp = IdentityProvider.objects.create(
            owner=cls.account,
            name='Entra ID for Helping Earth',
            slug='helpingearth',
            created_by='someadmin@dimagi.com',
            last_modified_by='someadmin@dimagi.com',
        )
        cls.idp.create_service_provider_certificate()
        email_domain = AuthenticatedEmailDomain.objects.create(
            identity_provider=cls.idp,
            email_domain='helpingearth.org'
        )
        UserExemptFromSingleSignOn.objects.create(
            username=cls.user_sso_exempt.username,
            email_domain=email_domain,
        )
        cls.idp.is_active = True
        cls.idp.save()

    def _get_login_response(self, username):
        return self.client.post(
            reverse('login'),
            {
                'auth-username': username,
                'auth-password': 'testpwd',
                'hq_login_view-current_step': 'auth',
            },
        )

    def _get_sso_login_status_response(self, username):
        return self.client.post(
            reverse('check_sso_login_status'),
            {
                'username': username,
            },
        )

    @override_settings(ENFORCE_SSO_LOGIN=True)
    def test_get_context_has_sso_enabled_when_sso_is_enforced(self):
        """
        Ensure that on a get request of the login view that `enforce_sso_login`
        in page's context is set to True if ENFORCE_SSO_LOGIN = True.
        """
        response = self.client.get(reverse('login'))
        self.assertTrue(response.context['enforce_sso_login'])

    @override_settings(ENFORCE_SSO_LOGIN=False)
    def test_get_context_has_sso_disabled_when_sso_is_not_enforced(self):
        """
        Ensure that on a get request of the login view that `enforce_sso_login`
        in page's context is set to False if ENFORCE_SSO_LOGIN = False.
        """
        response = self.client.get(reverse('login'))
        self.assertFalse(response.context['enforce_sso_login'])

    @override_settings(ENFORCE_SSO_LOGIN=False)
    def test_login_works_if_sso_not_enforced(self):
        """
        Ensure that even an SSO-required user can login through the login
        view if ENFORCE_SSO_LOGIN = False.
        """
        response = self._get_login_response(self.user_sso_required.username)
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(
            response.url,
            '/{}/'.format(settings.LOGIN_REDIRECT_URL)
        )

    @override_settings(ENFORCE_SSO_LOGIN=True)
    def test_login_is_redirected_if_sso_is_enforced(self):
        """
        Ensure that an SSO-required user is redirected to the appropriate
        login url for the Identity Provider if ENFORCE_SSO_LOGIN = True
        """
        response = self._get_login_response(self.user_sso_required.username)
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(
            response.url,
            self.idp.get_login_url(self.user_sso_required.username)
        )

    @override_settings(ENFORCE_SSO_LOGIN=True)
    def test_login_works_for_non_sso_users_when_sso_is_enforced(self):
        """
        Ensure that a user without an SSO requirement can login
        when ENFORCE_SSO_LOGIN = True
        """
        response = self._get_login_response(self.user_no_sso.username)
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(
            response.url,
            '/{}/'.format(settings.LOGIN_REDIRECT_URL)
        )

    @override_settings(ENFORCE_SSO_LOGIN=True)
    def test_login_works_for_sso_exempt_users_when_sso_is_enforced(self):
        """
        Ensure that a user exempt from the SSO requirement can login
        when ENFORCE_SSO_LOGIN = True
        """
        response = self._get_login_response(self.user_sso_exempt.username)
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(
            response.url,
            '/{}/'.format(settings.LOGIN_REDIRECT_URL)
        )

    def test_check_sso_login_status_for_non_sso_user(self):
        """
        Ensure that a user without an SSO login requirement returns the expected
        response for the check_sso_login_status view.
        """
        response = self._get_sso_login_status_response(self.user_no_sso.username)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(
            json.loads(response.content),
            {
                'is_sso_required': False,
                'sso_url': None,
                'continue_text': None,
            }
        )

    def test_check_sso_login_status_for_sso_user(self):
        """
        Ensure that an SSO user with an SSO login requirement returns the expected
        response for the check_sso_login_status view.
        """
        response = self._get_sso_login_status_response(self.user_sso_required.username)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(
            json.loads(response.content),
            {
                'is_sso_required': True,
                'sso_url': self.idp.get_login_url(self.user_sso_required.username),
                'continue_text': 'Continue to {}'.format(self.idp.name),
            }
        )

    def test_check_sso_login_status_for_sso_exempt_user(self):
        """
        Ensure that an SSO user exempt from theSSO login requirement returns
        the expected response for the check_sso_login_status view.
        """
        response = self._get_sso_login_status_response(self.user_sso_exempt.username)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(
            json.loads(response.content),
            {
                'is_sso_required': False,
                'sso_url': None,
                'continue_text': None,
            }
        )


class TestEmailAuthenticationFormWithSso(TestCase):

    @override_settings(ENFORCE_SSO_LOGIN=True)
    def test_form_has_extra_widget_attributes_when_sso_is_enforced(self):
        """
        Ensure that the attributes are inserted into the username and password
        widgets of the EmailAuthenticationForm when ENFORCE_SSO_LOGIN = True
        """
        form = EmailAuthenticationForm()
        self.assertEqual(
            form.fields['username'].widget.attrs,
            {
                'class': 'form-control',
                'data-bind': 'textInput: authUsername, onEnterKey: continueOnEnter',
                'placeholder': "Enter email address",
            }
        )
        self.assertEqual(
            form.fields['password'].widget.attrs,
            {
                'class': 'form-control',
                'placeholder': "Enter password",
            }
        )

    @override_settings(ENFORCE_SSO_LOGIN=False)
    def test_form_has_no_extra_widget_attributes_when_sso_is_not_enforced(self):
        """
        Ensure that the attributes remain the same on the widgets of username
        and password in EmailAuthenticationForm when ENFORCE_SSO_LOGIN = False
        """
        form = EmailAuthenticationForm()
        self.assertEqual(
            form.fields['username'].widget.attrs,
            {
                'class': 'form-control',
                'maxlength': 150,
            }
        )
        self.assertEqual(
            form.fields['password'].widget.attrs,
            {
                'class': 'form-control',
            }
        )

    def test_form_username_max_length(self):
        username = EmailAuthenticationForm().fields["username"]
        self.assertEqual(username.max_length, username.widget.attrs["maxlength"])
