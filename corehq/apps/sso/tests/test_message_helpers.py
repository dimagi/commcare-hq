from unittest import mock

from django.test import SimpleTestCase, RequestFactory

from corehq.apps.sso.utils.message_helpers import show_sso_login_success_or_error_messages


class TestShowSsoLoginSuccessOrErrorMessages(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get('/sso/test')
        self.request.sso_new_user_messages = {
            'success': [],
            'error': [],
        }

    @mock.patch('corehq.apps.sso.utils.message_helpers.messages.success')
    def test_success_message_is_shown(self, mock_messages_success):
        self.request.sso_new_user_messages['success'].append('is successful')
        show_sso_login_success_or_error_messages(self.request)
        self.assertEqual(mock_messages_success.call_count, 1)

    @mock.patch('corehq.apps.sso.utils.message_helpers.messages.error')
    def test_error_message_is_shown(self, mock_messages_error):
        self.request.sso_new_user_messages['error'].append('is error')
        self.request.sso_new_user_messages['error'].append('is another error')
        show_sso_login_success_or_error_messages(self.request)
        self.assertEqual(mock_messages_error.call_count, 2)

    @mock.patch('corehq.apps.sso.utils.message_helpers.messages.error')
    @mock.patch('corehq.apps.sso.utils.message_helpers.messages.success')
    def test_success_and_error_messages_are_shown(self, mock_messages_success, mock_messages_error):
        self.request.sso_new_user_messages['success'].append('is success')
        self.request.sso_new_user_messages['success'].append('is another success')
        self.request.sso_new_user_messages['error'].append('is error')
        show_sso_login_success_or_error_messages(self.request)
        self.assertEqual(mock_messages_success.call_count, 2)
        self.assertEqual(mock_messages_error.call_count, 1)
