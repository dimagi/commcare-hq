from datetime import datetime

from django.test import TestCase
from django.contrib.auth.models import User

from google.oauth2.credentials import Credentials

from corehq.apps.oauth.models import GoogleApiToken
from corehq.apps.oauth.utils import get_token, chunkify_data, load_credentials, stringify_credentials


class TestUtils(TestCase):

    def setUp(self):
        super(TestUtils, self).setUp()
        self.user = User()
        self.user.username = 'test@user.com'
        self.user.save()
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
        GoogleApiToken.objects.create(
            user=self.user,
            token=stringify_credentials(self.credentials)
        )

    def tearDown(self):
        self.credentials = None
        objects = GoogleApiToken.objects.get(user=self.user)
        objects.delete()
        self.user.delete()
        return super().tearDown()

    def test_stringify_credentials(self):
        desired_credentials = ('{"token": "token", "refresh_token": "refresh_token", "id_token": "id_token", '
        '"token_uri": "token_uri", "client_id": "client_id", "client_secret": "client_secret", '
        '"scopes": "scopes", "expiry": "2020-01-01 00:00:00"}')

        stringified_credentials = stringify_credentials(self.credentials)

        self.assertEqual(desired_credentials, stringified_credentials)

    def test_load_credentials(self):
        desired_credentials = self.credentials

        stringified_credentials = stringify_credentials(self.credentials)
        loaded_credentials = load_credentials(stringified_credentials)

        self.assertEqual(loaded_credentials.token, desired_credentials.token)

    def test_get_token(self):
        token = get_token(self.user)

        self.assertIsNotNone(token)

    def test_chunkify_data(self):
        desired_chunk_len = 4
        chunk_length = 20
        data = "This is a string of data that I want to break up in four chunks"

        chunkified_data = chunkify_data(data, chunk_length)

        self.assertEqual(len(chunkified_data), desired_chunk_len)
