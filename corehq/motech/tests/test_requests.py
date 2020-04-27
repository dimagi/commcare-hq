import random
import string
from unittest import skip

from django.conf import settings
from django.test import SimpleTestCase, TestCase

import requests
from mock import patch

from corehq.motech.auth import (
    AuthManager,
    BasicAuthManager,
    DigestAuthManager,
    OAuth2PasswordGrantTypeManager,
    dhis2_auth_settings,
)
from corehq.motech.const import REQUEST_TIMEOUT
from corehq.motech.requests import Requests, get_basic_requests

BASE_URL = 'http://dhis2.example.org/2.3.4/'
USERNAME = 'admin'
PASSWORD = 'district'
DOMAIN = 'test-domain'


class SendRequestTests(SimpleTestCase):

    def setUp(self):
        self.log_patcher = patch('corehq.motech.requests.RequestLog')
        self.log_patcher.start()

        self.request_patcher = patch.object(requests.Session, 'request')
        self.request_mock = self.request_patcher.start()

        self.auth_patcher = patch.object(BasicAuthManager, 'get_auth')
        get_auth_mock = self.auth_patcher.start()
        get_auth_mock.return_value = '<HTTPBasicAuthDummy>'

    def tearDown(self):
        self.auth_patcher.stop()
        self.request_patcher.stop()
        self.log_patcher.stop()

    def test_send_payload(self):
        payload = {'ham': ['spam', 'spam', 'spam']}
        req = get_basic_requests(DOMAIN, BASE_URL, USERNAME, PASSWORD)
        req.post('/api/dataValueSets', json=payload)
        self.request_mock.assert_called_with(
            'POST',
            'http://dhis2.example.org/2.3.4/api/dataValueSets',
            data=None,
            json=payload,
            headers={'Content-type': 'application/json', 'Accept': 'application/json'},
            auth='<HTTPBasicAuthDummy>',
            timeout=REQUEST_TIMEOUT,
        )

    def test_verify_ssl(self):
        req = get_basic_requests(
            DOMAIN, BASE_URL, USERNAME, PASSWORD, verify=False,
        )
        req.get('/api/me')
        self.request_mock.assert_called_with(
            'GET',
            'http://dhis2.example.org/2.3.4/api/me',
            allow_redirects=True,
            headers={'Accept': 'application/json'},
            auth='<HTTPBasicAuthDummy>',
            timeout=REQUEST_TIMEOUT,
            verify=False
        )


class SessionTests(SimpleTestCase):

    def setUp(self):
        self.log_patcher = patch('corehq.motech.requests.RequestLog')
        self.log_patcher.start()

        self.request_patcher = patch.object(requests.Session, 'request')
        self.request_patcher.start()

        self.close_patcher = patch.object(requests.Session, 'close')
        self.close_mock = self.close_patcher.start()

    def tearDown(self):
        self.close_patcher.stop()
        self.request_patcher.stop()
        self.log_patcher.stop()

    def test_with_session(self):
        """
        A context manager should use a single session
        """
        with get_basic_requests(
            DOMAIN, BASE_URL, USERNAME, PASSWORD
        ) as req:
            req.get('me')
            req.get('me')
            req.get('me')
        self.assertEqual(self.close_mock.call_count, 1)

    def test_without_session(self):
        """
        Calling without a context manager should use multiple sessions
        """
        req = get_basic_requests(
            DOMAIN, BASE_URL, USERNAME, PASSWORD
        )
        req.get('me')
        req.get('me')
        req.get('me')
        self.assertEqual(self.close_mock.call_count, 3)

    def test_with_and_without_session(self):
        """
        A context manager session is closed
        """
        with get_basic_requests(
            DOMAIN, BASE_URL, USERNAME, PASSWORD
        ) as req:
            req.get('me')
            req.get('me')
            req.get('me')
        req.get('me')
        self.assertEqual(self.close_mock.call_count, 2)


class NotifyErrorTests(SimpleTestCase):

    def setUp(self):
        self.mail_patcher = patch('corehq.motech.requests.send_mail_async')
        self.mail_mock = self.mail_patcher.start()

    def tearDown(self):
        self.mail_patcher.stop()

    def test_notify_error_no_address(self):
        """
        notify_error() should not try to send mail without addresses
        """
        req = get_basic_requests(DOMAIN, BASE_URL, USERNAME, PASSWORD)
        req.notify_error('foo')
        self.mail_mock.delay.assert_not_called()

    def test_notify_error_address_list(self):
        req = get_basic_requests(
            DOMAIN, BASE_URL, USERNAME, PASSWORD,
            notify_addresses=['foo@example.com', 'bar@example.com']
        )
        req.notify_error('foo')
        self.mail_mock.delay.assert_called_with(
            'MOTECH Error',
            (
                'foo\r\n'
                'Project space: test-domain\r\n'
                'Remote API base URL: http://dhis2.example.org/2.3.4/'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=['foo@example.com', 'bar@example.com']
        )


class AuthKwargTests(SimpleTestCase):

    def setUp(self):
        self.log_patcher = patch('corehq.motech.requests.RequestLog')
        self.log_patcher.start()

        self.request_patcher = patch.object(requests.Session, 'request')
        self.request_mock = self.request_patcher.start()

    def tearDown(self):
        self.request_patcher.stop()
        self.log_patcher.stop()

    def test_no_auth(self):
        auth_manager = AuthManager()
        reqs = Requests(DOMAIN, BASE_URL, auth_manager=auth_manager)
        reqs.get('me')
        kwargs = self.request_mock.call_args[1]
        self.assertNotIn('auth', kwargs)

    def test_basic_auth(self):
        auth_manager = BasicAuthManager(USERNAME, PASSWORD)
        reqs = Requests(DOMAIN, BASE_URL, auth_manager=auth_manager)
        reqs.get('me')
        kwargs = self.request_mock.call_args[1]
        auth_class = kwargs['auth'].__class__.__name__
        self.assertEqual(auth_class, 'HTTPBasicAuth')

    def test_digest_auth(self):
        auth_manager = DigestAuthManager(USERNAME, PASSWORD)
        reqs = Requests(DOMAIN, BASE_URL, auth_manager=auth_manager)
        reqs.get('me')
        kwargs = self.request_mock.call_args[1]
        auth_class = kwargs['auth'].__class__.__name__
        self.assertEqual(auth_class, 'HTTPDigestAuth')


@skip('This test uses third-party resources.')
class RequestsOAuth2Tests(TestCase):

    base_url = 'https://play.dhis2.org/dev'
    username = 'admin'
    password = 'district'
    fullname = 'John Traore'  # The name of user "admin" on play.dhis2.org

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        id_ = random.randint(10_000, 99_999)
        cls.client_id = f'client{id_}'
        client_name = f'Example Client {id_}'  # DHIS2 needs this to be unique
        cls.client_secret = mkpasswd(length=36)  # Mandatory length for DHIS2
        cls.client_uid = cls.add_dhis2_oauth2_client(client_name)

    @classmethod
    def tearDownClass(cls):
        get_basic_requests(
            DOMAIN, cls.base_url, cls.username, cls.password,
        ).delete(f'/api/oAuth2Clients/{cls.client_uid}')
        super().tearDownClass()

    @classmethod
    def add_dhis2_oauth2_client(cls, client_name):
        json_data = {
          "name": client_name,
          "cid": cls.client_id,
          "secret": cls.client_secret,
          "grantTypes": ["password", "refresh_token"]
        }
        resp = get_basic_requests(
            DOMAIN, cls.base_url, cls.username, cls.password,
        ).post('/api/oAuth2Clients', json=json_data, raise_for_status=True)
        return resp.json()['response']['uid']

    def test_oauth2_0_password(self):
        auth_manager = OAuth2PasswordGrantTypeManager(
            self.base_url,
            username=self.username,
            password=self.password,
            client_id=self.client_id,
            client_secret=self.client_secret,
            api_settings=dhis2_auth_settings,
        )
        with Requests(
            DOMAIN, self.base_url, auth_manager=auth_manager,
        ) as requests:
            # NOTE: Use Requests instance as a context manager so that
            #       it uses OAuth2Session.
            resp = requests.get('/api/me/')

            # Check API request succeeded
            self.assertEqual(resp.json()['name'], self.fullname)

            # Check token
            expected_keys = {'access_token', 'expires_at', 'expires_in',
                             'refresh_token', 'scope', 'token_type'}
            self.assertEqual(set(auth_manager.last_token), expected_keys)
            self.assertEqual(auth_manager.last_token['token_type'], 'bearer')


def mkpasswd(length):
    population = ''.join((
        string.ascii_uppercase,
        string.ascii_lowercase,
        string.digits,
    ))
    return ''.join(random.choices(population, k=length))
