from unittest.mock import patch, ANY
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.core.exceptions import ValidationError
from corehq.apps.users.models import WebUser

from ..forms import (
    LOGIN_ATTEMPTS_FOR_CLOUD_MESSAGE,
    EmailAuthenticationForm,
    HQAuthenticationTokenForm,
    HQBackupTokenForm,
)


class HQAuthenticationTokenFormTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.setUp_mocks()

    def setUp_mocks(self):
        clean_patcher = patch('corehq.apps.hqwebapp.forms.AuthenticationTokenForm.clean')
        self.mocked_clean = clean_patcher.start()
        self.mocked_clean.side_effect = ValidationError('Bad Token')
        self.addCleanup(clean_patcher.stop)

    def begin_login_attempt(self):
        user = WebUser(username='test_user')
        request = self.factory.post('/login')

        user_patcher = patch('corehq.apps.hqwebapp.forms.CouchUser.get_by_username', return_value=user)
        user_patcher.start()
        self.addCleanup(user_patcher.stop)

        return (user, request)

    def create_form_with_invalid_token(self, user, request):
        return HQAuthenticationTokenForm(user, 'device', request)

    @patch('corehq.apps.hqwebapp.forms.user_login_failed')
    def test_failed_authentication_sends_fully_formed_signal(self, mock_signal):
        user, request = self.begin_login_attempt()
        form = self.create_form_with_invalid_token(user, request)

        with self.assertRaises(ValidationError):
            form.clean()

        expected_credentials = {'username': user.username}
        mock_signal.send.assert_called_once_with(credentials=expected_credentials, request=request,
            token_failure=True, sender=ANY)


class HQBackupTokenFormTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.setUp_mocks()

    def setUp_mocks(self):
        clean_patcher = patch('corehq.apps.hqwebapp.forms.BackupTokenForm.clean')
        self.mocked_clean = clean_patcher.start()
        self.mocked_clean.side_effect = ValidationError('Bad Token')
        self.addCleanup(clean_patcher.stop)

    def begin_login_attempt(self):
        user = WebUser(username='test_user')
        request = self.factory.post('/login')

        user_patcher = patch('corehq.apps.hqwebapp.forms.CouchUser.get_by_username', return_value=user)
        user_patcher.start()
        self.addCleanup(user_patcher.stop)

        return (user, request)

    def create_form_with_invalid_token(self, user, request):
        return HQBackupTokenForm(user, 'device', request)

    @patch('corehq.apps.hqwebapp.forms.user_login_failed')
    def test_failed_clean_sends_fully_formed_signal(self, mock_signal):
        user, request = self.begin_login_attempt()
        form = self.create_form_with_invalid_token(user, request)

        with self.assertRaises(ValidationError):
            form.clean()

        expected_credentials = {'username': user.username}
        mock_signal.send.assert_called_once_with(credentials=expected_credentials, request=request,
            token_failure=True, sender=ANY)


class TestEmailAuthenticationFormValidationError(TestCase):
    def create_form(self, request=None, can_select_server=None):
        form = EmailAuthenticationForm(
            request=request,
            can_select_server=can_select_server,
            data={
                'username': 'anyemail@example.com',
                'password': 'badpassword',
            },
        )
        return form

    def run_form_and_assert(
        self, request=None, can_select_server=None, expected_message=None
    ):
        form = self.create_form(request=request, can_select_server=can_select_server)
        form.full_clean()
        assert not form.is_valid()
        non_field_errors = form.non_field_errors().as_data()
        assert len(non_field_errors) == 1
        assert isinstance(non_field_errors[0], ValidationError)
        assert expected_message in non_field_errors[0].message

    def test_cloud_location_message_when_at_attempts_const(self):
        request = RequestFactory().get('/')
        request.session = {'login_attempts': LOGIN_ATTEMPTS_FOR_CLOUD_MESSAGE}
        message = "Still having trouble?"
        self.run_form_and_assert(
            request=request,
            can_select_server=True,
            expected_message=message,
        )

    def test_original_message_when_below_attempts_const(self):
        request = RequestFactory().get('/')
        request.session = {'login_attempts': LOGIN_ATTEMPTS_FOR_CLOUD_MESSAGE - 1}
        message = "Please enter a correct %(username)s and password."
        self.run_form_and_assert(
            request=request,
            can_select_server=True,
            expected_message=message,
        )

    def test_original_message_if_not_can_select_server(self):
        request = RequestFactory().get('/')
        request.session = {'login_attempts': LOGIN_ATTEMPTS_FOR_CLOUD_MESSAGE}
        message = "Please enter a correct %(username)s and password."
        self.run_form_and_assert(
            request=request,
            can_select_server=False,
            expected_message=message,
        )

    def test_original_message_if_no_request_object(self):
        self.run_form_and_assert(
            request=None,
            can_select_server=True,
            expected_message="Please enter a correct %(username)s and password.",
        )
