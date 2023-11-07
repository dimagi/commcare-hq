import random
import string
from unittest import skip

from django.test import SimpleTestCase, TestCase

import requests
from unittest.mock import patch

from corehq.motech.auth import AuthManager, BasicAuthManager, DigestAuthManager
from corehq.motech.const import OAUTH2_PWD, REQUEST_TIMEOUT
from corehq.motech.models import ConnectionSettings
from corehq.motech.requests import get_basic_requests
from corehq.motech.views import ConnectionSettingsListView
from corehq.util.urlvalidate.urlvalidate import PossibleSSRFAttempt
from corehq.util.urlvalidate.ip_resolver import CannotResolveHost
from corehq.util.view_utils import absolute_reverse

BASE_URL = 'http://www.example.com/2.3.4/'
USERNAME = 'admin'
PASSWORD = 'district'
DOMAIN = 'test-domain'


def noop_logger(*args, **kwargs):
    pass


class SendRequestTests(SimpleTestCase):

    def setUp(self):
        self.request_patcher = patch.object(requests.Session, 'request')
        self.auth_patcher = patch.object(BasicAuthManager, 'get_auth', return_value='<HTTPBasicAuthDummy>')

    def test_send_payload(self):
        payload = {'ham': ['spam', 'spam', 'spam']}
        req = get_basic_requests(
            DOMAIN, BASE_URL, USERNAME, PASSWORD,
            logger=noop_logger
        )
        with self.auth_patcher, self.request_patcher as request_mock:
            req.post('/api/dataValueSets', json=payload)
            request_mock.assert_called_with(
                'POST',
                'http://www.example.com/2.3.4/api/dataValueSets',
                data=None,
                json=payload,
                headers={'Content-type': 'application/json', 'Accept': 'application/json'},
                timeout=REQUEST_TIMEOUT,
            )

    def test_verify_ssl(self):
        req = get_basic_requests(
            DOMAIN, BASE_URL, USERNAME, PASSWORD,
            verify=False, logger=noop_logger,
        )
        with self.auth_patcher, self.request_patcher as request_mock:
            req.get('/api/me')
            request_mock.assert_called_with(
                'GET',
                'http://www.example.com/2.3.4/api/me',
                allow_redirects=True,
                headers={'Accept': 'application/json'},
                timeout=REQUEST_TIMEOUT,
                verify=False
            )

    def test_bad_url(self):
        payload = {'ham': ['spam', 'spam', 'spam']}
        req = get_basic_requests(
            DOMAIN, 'http://10.11.12.13/', USERNAME, PASSWORD,
            logger=noop_logger
        )
        with self.assertRaises(PossibleSSRFAttempt):
            req.post('/api/dataValueSets', json=payload)

    def test_unknown_url(self):
        payload = {'ham': ['spam', 'spam', 'spam']}
        req = get_basic_requests(
            DOMAIN, 'http://not-a-valid-host.com', USERNAME, PASSWORD,
            logger=noop_logger
        )
        with self.assertRaises(CannotResolveHost):
            req.post('/api/dataValueSets', json=payload)


class SessionTests(SimpleTestCase):

    def setUp(self):
        self.request_patcher = patch.object(requests.Session, 'request')
        self.request_patcher.start()

        self.close_patcher = patch.object(requests.Session, 'close')
        self.close_mock = self.close_patcher.start()

    def tearDown(self):
        self.close_patcher.stop()
        self.request_patcher.stop()

    def test_with_session(self):
        """
        A context manager should use a single session
        """
        with get_basic_requests(
            DOMAIN, BASE_URL, USERNAME, PASSWORD,
            logger=noop_logger
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
            DOMAIN, BASE_URL, USERNAME, PASSWORD,
            logger=noop_logger
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
            DOMAIN, BASE_URL, USERNAME, PASSWORD,
            logger=noop_logger
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
        connection_settings_url = absolute_reverse(
            ConnectionSettingsListView.urlname, args=[DOMAIN])
        req = get_basic_requests(
            DOMAIN, BASE_URL, USERNAME, PASSWORD,
            notify_addresses=['foo@example.com', 'bar@example.com']
        )
        req.notify_error('foo')
        self.mail_mock.delay.assert_called_with(
            'MOTECH Error',
            (
                'foo\r\n'
                '\r\n'
                'Project space: test-domain\r\n'
                'Remote API base URL: http://www.example.com/2.3.4/\r\n'
                '\r\n'
                '*Why am I getting this email?*\r\n'
                'This address is configured in CommCare HQ as a notification '
                'address for integration errors.\r\n'
                '\r\n'
                '*How do I unsubscribe?*\r\n'
                'Open Connection Settings in CommCare HQ '
                f'({connection_settings_url}) and remove your email address '
                'from the "Addresses to send notifications" field for remote '
                'connections. If necessary, please provide an alternate '
                'address.'
            ),
            recipient_list=['foo@example.com', 'bar@example.com'],
            domain='test-domain', use_domain_gateway=True
        )


class AuthClassTests(SimpleTestCase):

    def test_no_auth(self):
        auth_manager = AuthManager()
        auth = auth_manager.get_auth()
        self.assertIsNone(auth)

    def test_basic_auth(self):
        auth_manager = BasicAuthManager(USERNAME, PASSWORD)
        auth = auth_manager.get_auth()
        self.assertEqual(auth.__class__.__name__, 'HTTPBasicAuth')

    def test_digest_auth(self):
        auth_manager = DigestAuthManager(USERNAME, PASSWORD)
        auth = auth_manager.get_auth()
        self.assertEqual(auth.__class__.__name__, 'HTTPDigestAuth')


@skip('This test uses third-party resources.')
class RequestsOAuth2Tests(TestCase):

    base_url = 'https://play.dhis2.org/dev'
    username = 'admin'
    password = 'district'
    fullname = 'John Traore'  # The name of user "admin" on play.dhis2.org

    def setUp(self):
        id_ = random.randint(10_000, 99_999)
        client_id = f'client{id_}'
        client_name = f'Example Client {id_}'  # DHIS2 needs this to be unique
        client_secret = mkpasswd(length=36)  # Mandatory length for DHIS2
        self.client_uid = self.add_dhis2_oauth2_client(
            client_name, client_id, client_secret
        )
        self.connection_settings = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name=self.base_url,
            url=self.base_url,
            auth_type=OAUTH2_PWD,
            api_auth_settings='dhis2_auth_settings',
            username=self.username,
            password=self.password,
            client_id=client_id,
            client_secret=client_secret,
        )

    def tearDown(self):
        self.connection_settings.delete()
        self.delete_dhis2_oauth2_client()

    def add_dhis2_oauth2_client(self, client_name, client_id, client_secret):
        json_data = {
            "name": client_name,
            "cid": client_id,
            "secret": client_secret,
            "grantTypes": ["password", "refresh_token"]
        }
        resp = get_basic_requests(
            DOMAIN, self.base_url, self.username, self.password,
            logger=noop_logger,
        ).post('/api/oAuth2Clients', json=json_data, raise_for_status=True)
        return resp.json()['response']['uid']

    def delete_dhis2_oauth2_client(self):
        get_basic_requests(
            DOMAIN, self.base_url, self.username, self.password,
            logger=noop_logger,
        ).delete(f'/api/oAuth2Clients/{self.client_uid}')

    def test_oauth2_0_password(self):
        req = self.connection_settings.get_requests(logger=noop_logger)
        resp = req.get('/api/me/')

        # Check API request succeeded
        self.assertEqual(resp.json()['name'], self.fullname)

        # Check token
        expected_keys = {'access_token', 'expires_at', 'expires_in',
                         'refresh_token', 'scope', 'token_type'}
        self.assertEqual(set(self.connection_settings.last_token),
                         expected_keys)
        self.assertEqual(self.connection_settings.last_token['token_type'],
                         'bearer')


def mkpasswd(length):
    population = ''.join((
        string.ascii_uppercase,
        string.ascii_lowercase,
        string.digits,
    ))
    return ''.join(random.choices(population, k=length))
