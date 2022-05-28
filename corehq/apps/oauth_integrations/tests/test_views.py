from datetime import datetime

from unittest.mock import patch

from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth.models import User

from google.oauth2.credentials import Credentials
from corehq.apps.oauth_integrations.utils import get_token, load_credentials, stringify_credentials

from corehq.apps.oauth_integrations.views.google import google_sheet_oauth_redirect, google_sheet_oauth_callback
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.oauth_integrations.models import GoogleApiToken


class TestViews(TestCase):

    def test_google_sheet_oauth_redirect_without_credentials(self):
        self.mocked_get_url.return_value = "googleredirecturl.com"
        request = self.factory.get('')
        request.user = self.user

        response = google_sheet_oauth_redirect(request, self.domain)

        self.assertEqual(response.url, 'googleredirecturl.com')

    def test_google_sheet_oauth_redirect_with_credentials(self):
        self.setUp_credentials()
        self.mocked_refresh_credentials.return_value = self.create_new_credentials(token="new_token")
        self.mocked_get_url.return_value = "googleredirecturl.com"
        request = self.factory.get('')
        request.user = self.user

        response = google_sheet_oauth_redirect(request, self.domain)
        stringified_creds = get_token(self.user)
        creds = load_credentials(stringified_creds.token)

        self.assertEqual(response.url, "placeholder.com")
        self.assertEqual(creds.token, 'new_token')

    @override_settings(GOOGLE_OAUTH_CONFIG={
        "web": {
            "client_id": "test_id",
            "project_id": "test_project_id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": "test_client_secret"}
    })
    def test_google_sheet_oauth_callback_with_token_updates_credentials(self):
        self.setUp_credentials()
        self.mocked_get_token.return_value = stringify_credentials(self.create_new_credentials("new_token"))
        request = self.factory.get('', {'state': 101})
        request.user = self.user

        google_sheet_oauth_callback(request, self.domain)

        stringified_creds = get_token(self.user)
        creds = load_credentials(stringified_creds.token)

        self.assertEqual(creds.token, "new_token")

    @override_settings(GOOGLE_OAUTH_CONFIG={
        "web": {
            "client_id": "test_id",
            "project_id": "test_project_id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": "test_client_secret"}
    })
    def test_google_sheet_oauth_callback_without_token_creates_credentials(self):
        self.mocked_get_token.return_value = stringify_credentials(self.create_new_credentials("new_token"))
        request = self.factory.get('', {'state': 101})
        request.user = self.user

        google_sheet_oauth_callback(request, self.domain)

        creds = get_token(self.user)

        self.assertIsNotNone(creds)

    def setUp(self):
        self.setUp_mocks()
        self.factory = RequestFactory()
        self.user = User()
        self.user.username = 'test@user.com'
        self.user.save()

        self.domain = create_domain("test_domain")

        self.credentials = Credentials(
            token="token",
            refresh_token="refresh_token",
            id_token="id_token",
            token_uri="token_uri",
            client_id="client_id",
            client_secret="client_secret",
            scopes="scopes",
            expiry=datetime(2020, 1, 1)
        )
        self.stringified_token = stringify_credentials(self.credentials)

        return super().setUp()

    def tearDown(self):
        token = get_token(self.user)
        if token:
            token.delete()
        self.user.delete()
        self.domain.delete()

        return super().tearDown()

    def setUp_mocks(self):
        get_url_from_google_patcher = patch('corehq.apps.oauth_integrations.views.google.get_url_from_google')
        refresh_credentials_patcher = patch('corehq.apps.oauth_integrations.views.google.refresh_credentials')
        get_token_patcher = patch('corehq.apps.oauth_integrations.views.google.get_token_from_google')

        self.mocked_get_url = get_url_from_google_patcher.start()
        self.mocked_refresh_credentials = refresh_credentials_patcher.start()
        self.mocked_get_token = get_token_patcher.start()

        self.addCleanup(get_url_from_google_patcher.stop)
        self.addCleanup(refresh_credentials_patcher.stop)
        self.addCleanup(get_token_patcher.stop)

    def setUp_credentials(self):
        return GoogleApiToken.objects.create(
            user=self.user,
            token=self.stringified_token
        )

    def create_new_credentials(self, token="new_token"):
        credentials = Credentials(
            token=token,
            refresh_token="refresh_token",
            id_token="id_token",
            token_uri="token_uri",
            client_id="client_id",
            client_secret="client_secret",
            scopes="scopes",
            expiry=datetime(2020, 1, 1)
        )

        return credentials
