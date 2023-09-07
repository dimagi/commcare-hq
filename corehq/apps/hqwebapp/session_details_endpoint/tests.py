import datetime
import json
import pytz

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from django.utils.dateparse import parse_datetime

from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from corehq.util.hmac_request import get_hmac_digest
from corehq.util.test_utils import flag_enabled, softer_assert


class SessionDetailsViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(SessionDetailsViewTest, cls).setUpClass()
        cls.domain = Domain(name="toyland", is_active=True)
        cls.domain.save()
        cls.couch_user = CommCareUser.create(cls.domain.name, 'bunkey', '123', None, None)
        cls.sql_user = cls.couch_user.get_django_user()

        cls.expected_response = {
            'username': cls.sql_user.username,
            'djangoUserId': cls.sql_user.pk,
            'superUser': cls.sql_user.is_superuser,
            'authToken': None,
            'domains': [cls.domain.name],
            'anonymous': False,
            'enabled_toggles': [],
            'enabled_previews': [],
        }
        cls.url = reverse('session_details')

    def setUp(self):
        # logs in the mobile worker every test so a new session is setup
        self.client = Client()
        self.client.login(username='bunkey', password='123')

        self.session = self.client.session
        self.session.save()
        self.session_key = self.session.session_key

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super(SessionDetailsViewTest, cls).tearDownClass()

    def _assert_session_expiry_in_minutes(self, expected_minutes, actual_time_string):
        delta = parse_datetime(actual_time_string) - datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        diff_in_minutes = delta.days * 24 * 60 + delta.seconds / 60
        self.assertEqual(expected_minutes, round(diff_in_minutes))

    @softer_assert()
    def test_session_details_view(self):
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertJSONEqual(response.content, self.expected_response)

    @softer_assert()
    def test_session_details_view_expired_session(self):
        self.session.set_expiry(-1)  # 1 second in the past
        self.session.save()
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        self.assertEqual(404, response.status_code)

    @softer_assert()
    def test_session_details_view_updates_session(self):
        expired_date = self.session.get_expiry_date()
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertGreater(self.session.get_expiry_date(), expired_date)

    @flag_enabled('SECURE_SESSION_TIMEOUT')
    def test_secure_sessions(self):

        def _assertSecureSessionExpiry(previous_expiry, timeout_in_minutes):
            self.assertEqual(True, self.client.session.get('secure_session'))
            self.assertEqual(timeout_in_minutes, self.client.session.get('secure_session_timeout'))
            self.assertNotEqual(previous_expiry, self.client.session.get_expiry_date())
            expiring_in = (self.client.session.get_expiry_date() - datetime.datetime.utcnow()).seconds
            self.assertGreater(expiring_in, timeout_in_minutes * 60 - 2)
            self.assertLess(expiring_in, timeout_in_minutes * 60 + 2)

        # Turn on secure sessions
        self.domain.secure_sessions = True
        self.domain.save()

        # Sessions should now be secure and use timeout from settings
        expired_date = self.session.get_expiry_date()
        self.client.get(reverse('domain_homepage', args=[self.domain.name]))
        _assertSecureSessionExpiry(expired_date, settings.SECURE_TIMEOUT)

        # Turn on customized timeout
        custom_timeout = 10
        self.domain.secure_sessions_timeout = custom_timeout
        self.domain.save()

        # Request a domain-specific page so the domain-specific timeout kicks in
        expired_date = self.session.get_expiry_date()
        self.client.get(reverse('domain_homepage', args=[self.domain.name]))
        _assertSecureSessionExpiry(expired_date, custom_timeout)

        # Request a non-domain-specific page, which still uses the domain-specific timeout saved in the session
        expired_date = self.session.get_expiry_date()
        self.client.get(reverse('ping_session'))
        _assertSecureSessionExpiry(expired_date, custom_timeout)

        # Test the session details view itself
        expired_date = self.session.get_expiry_date()
        data = json.dumps({'sessionId': self.session_key, 'domain': self.domain.name})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        self.assertEqual(200, response.status_code)
        _assertSecureSessionExpiry(expired_date, custom_timeout)

        # Going back to insecure sessions requires a logout to create a new session
        self.domain.secure_sessions_timeout = None
        self.domain.secure_sessions = False
        self.domain.save()
        self.client.logout()
        self.client.login(username='bunkey', password='123')
        self.client.get(reverse('domain_homepage', args=[self.domain.name]))
        self.assertEqual(False, self.client.session.get('secure_session'))
        self.assertEqual(settings.INACTIVITY_TIMEOUT, self.client.session.get('secure_session_timeout'))

    def test_ping_login_unauth_user(self):
        client = Client()
        client.login(username='jackalope', password='456')
        response = client.get(reverse('ping_login'))
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIsNone(data['session_expiry'])
        self.assertIsNone(data['secure_session_timeout'])
        self.assertFalse(data['secure_session'])
        self.assertEqual("", data['username'])

    def test_ping_login_auth_user(self):
        client = Client()
        client.login(username=self.couch_user.username, password='123')

        # First ping after login via client.login: authorized but no session expiry
        response = client.get(reverse('ping_login'))
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIsNone(data['session_expiry'])
        self.assertIsNone(data['secure_session_timeout'])
        self.assertFalse(data['secure_session'])
        self.assertEqual(self.couch_user.username, data['username'])

        # Request a page and then re-ping: session expiry should be based on INACTIVITY_TIMEOUT
        client.get(reverse('bsd_license'))
        response = client.get(reverse('ping_login'))
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(self.couch_user.username, data['username'])
        self.assertFalse(data['secure_session'])
        self.assertEqual(settings.INACTIVITY_TIMEOUT, data['secure_session_timeout'])
        self._assert_session_expiry_in_minutes(settings.INACTIVITY_TIMEOUT, data['session_expiry'])

        # Ping some more, session_expiry should not change
        session_expiry = data['session_expiry']
        client.get(reverse('ping_login'))
        response = client.get(reverse('ping_login'))
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(self.couch_user.username, data['username'])
        self.assertEqual(session_expiry, data['session_expiry'])

        # Request a normal page, session_expiry should update
        client.get(reverse('bsd_license'))
        response = client.get(reverse('ping_login'))
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(self.couch_user.username, data['username'])
        self.assertIsNotNone(data['session_expiry'])
        self.assertNotEqual(session_expiry, data['session_expiry'])

    def test_with_hmac_signing(self):
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})
        header_value = get_hmac_digest(settings.FORMPLAYER_INTERNAL_AUTH_KEY, data)
        response = Client().post(
            self.url,
            data,
            content_type="application/json",
            HTTP_X_MAC_DIGEST=header_value
        )
        self.assertEqual(200, response.status_code)
        self.assertJSONEqual(response.content, self.expected_response)

    def test_with_hmac_signing_fail(self):
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})

        response = Client().post(
            self.url,
            data,
            content_type="application/json",
            HTTP_X_MAC_DIGEST='bad signature'
        )
        self.assertEqual(401, response.status_code)

    @softer_assert()
    @flag_enabled('SECURE_SESSION_TIMEOUT')
    @flag_enabled('CALC_XPATHS', is_preview=True)
    def test_session_details_view_toggles(self):
        toggles.all_toggles()
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        self.assertEqual(200, response.status_code)
        expected_response = self.expected_response.copy()
        expected_response['enabled_toggles'] = ['SECURE_SESSION_TIMEOUT']
        expected_response['enabled_previews'] = ['CALC_XPATHS']
        self.assertJSONEqual(response.content, expected_response)


def _post_with_hmac(url, data, client=None, **kwargs):
    header_value = get_hmac_digest(settings.FORMPLAYER_INTERNAL_AUTH_KEY, data)
    client = client or Client()
    return client.post(url, data, HTTP_X_MAC_DIGEST=header_value, **kwargs)
