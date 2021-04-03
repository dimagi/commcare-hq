from unittest.mock import patch, ANY
from django.test import RequestFactory, SimpleTestCase
from django.core.exceptions import ValidationError
from corehq.apps.users.models import WebUser

from ..forms import HQAuthenticationTokenForm, HQBackupTokenForm


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
