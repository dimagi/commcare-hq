import base64
import hashlib
import hmac
import json

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from corehq.apps.users.models import CommCareUser
from corehq.util.hmac_request import get_hmac_digest
from corehq.util.test_utils import softer_assert


class SessionDetailsViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(SessionDetailsViewTest, cls).setUpClass()
        cls.couch_user = CommCareUser.create('toyland', 'bunkey', '123')
        cls.sql_user = cls.couch_user.get_django_user()

        cls.expected_response = {
            'username': cls.sql_user.username,
            'djangoUserId': cls.sql_user.pk,
            'superUser': cls.sql_user.is_superuser,
            'authToken': None,
            'domains': ['toyland'],
            'anonymous': False
        }
        cls.url = reverse('session_details')

    def setUp(self):
        # logs in the mobile worker every test so a new session is setup
        client = Client()
        client.login(username='bunkey', password='123')

        self.session = client.session
        self.session.save()
        self.session_key = self.session.session_key

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete()
        super(SessionDetailsViewTest, cls).tearDownClass()

    @override_settings(DEBUG=True)
    @softer_assert()
    def test_session_details_view(self):
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})
        response = Client().post(self.url, data, content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertJSONEqual(response.content, self.expected_response)

    @override_settings(DEBUG=True)
    @softer_assert()
    def test_session_details_view_expired_session(self):
        self.session.set_expiry(-1)  # 1 second in the past
        self.session.save()
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})
        response = Client().post(self.url, data, content_type="application/json")
        self.assertEqual(404, response.status_code)

    @override_settings(DEBUG=True)
    @softer_assert()
    def test_session_details_view_updates_session(self):
        expired_date = self.session.get_expiry_date()
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})
        response = Client().post(self.url, data, content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertGreater(self.session.get_expiry_date(), expired_date)

    @override_settings(DEBUG=True)
    def test_ping_login_unauth_user(self):
        client = Client()
        client.login(username='jackalope', password='456')
        response = client.get(reverse('ping_login'))
        self.assertEqual(200, response.status_code)
        self.assertJSONEqual(response.content, {
            "success": False,
            "last_request": None,
            "username": "",
        })

    @override_settings(DEBUG=True)
    def test_ping_login_auth_user(self):
        client = Client()
        client.login(username=self.couch_user.username, password='123')

        # First ping after login: authorized but no previous request
        response = client.get(reverse('ping_login'))
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertJSONEqual(response.content, {
            "success": True,
            "last_request": None,
            "username": self.couch_user.username
        })

        # Request a page and then re-ping: last_request should exist
        client.get(reverse('bsd_license'))
        response = client.get(reverse('ping_login'))
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(self.couch_user.username, data['username'])
        self.assertIsNotNone(data['last_request'])
        last_request = data['last_request']

        # Ping some more, last_request should not change
        client.get(reverse('ping_login'))
        response = client.get(reverse('ping_login'))
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(self.couch_user.username, data['username'])
        self.assertEqual(last_request, data['last_request'])

        # Request a normal page, last_request should update
        client.get(reverse('bsd_license'))
        response = client.get(reverse('ping_login'))
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(self.couch_user.username, data['username'])
        self.assertIsNotNone(data['last_request'])
        self.assertNotEqual(last_request, data['last_request'])

    @override_settings(FORMPLAYER_INTERNAL_AUTH_KEY='123abc', DEBUG=False)
    def test_with_hmac_signing(self):
        assert not settings.DEBUG
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})
        header_value = get_hmac_digest(b'123abc', data)
        response = Client().post(
            self.url,
            data,
            content_type="application/json",
            HTTP_X_MAC_DIGEST=header_value
        )
        self.assertEqual(200, response.status_code)
        self.assertJSONEqual(response.content, self.expected_response)

    @override_settings(FORMPLAYER_INTERNAL_AUTH_KEY='123abc', DEBUG=False)
    def test_with_hmac_signing_fail(self):
        assert not settings.DEBUG
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})

        response = Client().post(
            self.url,
            data,
            content_type="application/json",
            HTTP_X_MAC_DIGEST='bad signature'
        )
        self.assertEqual(401, response.status_code)
