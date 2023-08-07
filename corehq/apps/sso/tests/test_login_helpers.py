from unittest import mock

from django.test import TestCase, RequestFactory

from corehq.apps.domain.exceptions import NameUnavailableException
from corehq.apps.domain.models import Domain
from corehq.apps.registration.forms import RegisterWebUserForm
from corehq.apps.registration.models import AsyncSignupRequest
from corehq.apps.sso.tests.generator import create_request_session
from corehq.apps.sso.utils.login_helpers import process_async_signup_requests
from corehq.apps.users.models import WebUser


def _name_unavailable_for_domain_request(*args, **kwargs):
    raise NameUnavailableException()


class TestProcessAsyncSignupRequests(TestCase):
    """
    These tests ensure that process_async_signup_requests correctly processes AsyncSignupRequests after a
    successful login
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.existing_domain = Domain.get_or_create_with_name(
            "existing-domain-sso-001",
            is_active=True
        )

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get('/sso/test')
        create_request_session(self.request)

    @classmethod
    def tearDownClass(cls):
        cls.existing_domain.delete()
        super().tearDownClass()

    @staticmethod
    def _get_signup_form(username, project_name):
        reg_form = RegisterWebUserForm()
        reg_form.cleaned_data = {
            'email': username,
            'phone_number': '+15555555555',
            'project_name': project_name,
            'persona': 'Other',
            'persona_other': "for tests",
        }
        return reg_form

    @mock.patch('corehq.apps.sso.utils.login_helpers.request_new_domain')
    def test_new_domain_is_created_and_request_is_deleted(self, mock_request_new_domain):
        username = 'm@vaultwax.com'
        new_domain_name = 'test-vault-001'
        reg_form = self._get_signup_form(username, new_domain_name)
        AsyncSignupRequest.create_from_registration_form(reg_form)

        self.assertTrue(AsyncSignupRequest.objects.filter(username=username).exists())
        user = WebUser.create(self.existing_domain.name, username, 'testpwd', None, None)
        user.is_authenticated = True
        self.request.user = user
        process_async_signup_requests(self.request, user)

        self.assertEqual(mock_request_new_domain.call_count, 1)
        self.assertFalse(AsyncSignupRequest.objects.filter(username=username).exists())

    @mock.patch('corehq.apps.sso.utils.login_helpers.request_new_domain', _name_unavailable_for_domain_request)
    @mock.patch('corehq.apps.sso.utils.login_helpers.messages.error')
    def test_error_message_is_raised_if_domain_exists(self, django_error_messages):
        username = 'a@vaultwax.com'
        reg_form = self._get_signup_form(username, self.existing_domain.name)
        AsyncSignupRequest.create_from_registration_form(reg_form)

        user = WebUser.create(self.existing_domain.name, username, 'testpwd', None, None)
        user.is_authenticated = True
        process_async_signup_requests(self.request, user)

        self.assertEqual(django_error_messages.call_count, 1)
        self.assertFalse(AsyncSignupRequest.objects.filter(username=username).exists())
