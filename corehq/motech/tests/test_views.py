from unittest.mock import Mock, patch

from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.motech.const import (
    BASIC_AUTH,
    OAUTH2_CLIENT,
    PASSWORD_PLACEHOLDER,
)
from corehq.motech.forms import ConnectionSettingsForm
from corehq.motech.requests import Requests

DOMAIN = 'test-motech-views'
USERNAME = 'test@motech-views.com'
PASSWORD = 'password'


class TestConnectionSettingsView(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(DOMAIN)
        cls.addClassCleanup(cls.domain.delete)
        cls.user = WebUser.create(
            DOMAIN, USERNAME, PASSWORD, created_by=None, created_via=None,
        )
        cls.user.is_superuser = True
        cls.user.save()
        cls.addClassCleanup(cls.user.delete, cls.domain.name, None)

        cls.privilege_patch = patch(
            'corehq.motech.views.has_privilege', return_value=True,
        )
        cls.privilege_patch.start()
        cls.addClassCleanup(cls.privilege_patch.stop)

    def setUp(self):
        super().setUp()
        self.client.login(username=USERNAME, password=PASSWORD)

    def _post(self, data):
        return self.client.post(
            reverse('test_connection_settings', kwargs={'domain': DOMAIN}),
            data,
        )

    def test_basic_auth_uses_password_from_form_data(self):
        post_data = {
            'name': 'basic-conn',
            'url': 'http://example.com',
            'auth_type': BASIC_AUTH,
            'username': 'user',
            'plaintext_password': 'typed-password',
            'notify_addresses_str': 'ops@example.com',
        }
        assert ConnectionSettingsForm(domain=DOMAIN, data=post_data).is_valid()

        with patch.object(Requests, 'get', autospec=True) as mock_get:
            mock_get.return_value = Mock(status_code=200, text='')
            self._post(post_data)

        requests_instance = mock_get.call_args.args[0]
        assert requests_instance.auth_manager.password == 'typed-password'

    def test_oauth2_client_uses_client_secret_from_form_data(self):
        post_data = {
            'name': 'oauth-conn',
            'url': 'http://example.com',
            'auth_type': OAUTH2_CLIENT,
            'client_id': 'client-id',
            'plaintext_client_secret': 'form-secret',
            'token_url': 'http://example.com/token',
            'notify_addresses_str': 'ops@example.com',
        }
        assert ConnectionSettingsForm(domain=DOMAIN, data=post_data).is_valid()

        with patch.object(Requests, 'get', autospec=True) as mock_get:
            mock_get.return_value = Mock(status_code=200, text='')
            self._post(post_data)

        requests_instance = mock_get.call_args.args[0]
        assert requests_instance.auth_manager.client_secret == 'form-secret'

    def test_basic_auth_rejects_password_placeholder(self):
        post_data = {
            'name': 'basic-conn',
            'url': 'http://example.com',
            'auth_type': BASIC_AUTH,
            'username': 'user',
            'plaintext_password': PASSWORD_PLACEHOLDER,
            'notify_addresses_str': 'ops@example.com',
        }

        with patch.object(Requests, 'get', autospec=True) as mock_get:
            response = self._post(post_data)

        assert response.json() == {
            'success': False,
            'response': 'Please enter API password again.',
        }
        mock_get.assert_not_called()

    def test_oauth2_client_rejects_client_secret_placeholder(self):
        post_data = {
            'name': 'oauth-conn',
            'url': 'http://example.com',
            'auth_type': OAUTH2_CLIENT,
            'client_id': 'client-id',
            'plaintext_client_secret': PASSWORD_PLACEHOLDER,
            'token_url': 'http://example.com/token',
            'notify_addresses_str': 'ops@example.com',
        }

        with patch.object(Requests, 'get', autospec=True) as mock_get:
            response = self._post(post_data)

        assert response.json() == {
            'success': False,
            'response': 'Please enter client secret again.',
        }
        mock_get.assert_not_called()
