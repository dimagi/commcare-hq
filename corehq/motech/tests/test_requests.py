import json
import random
import string
from unittest import skip

from django.conf import settings
from django.test import SimpleTestCase, TestCase

import requests
from mock import Mock, patch

from corehq.motech.auth import (
    AuthManager,
    BasicAuthManager,
    DigestAuthManager,
    OAuth2PasswordGrantTypeManager,
    dhis2_auth_settings,
)
from corehq.motech.const import (
    REQUEST_TIMEOUT,
)
from corehq.motech.requests import Requests, get_basic_requests

TEST_API_URL = 'http://localhost:9080/api/'
TEST_API_USERNAME = 'admin'
TEST_API_PASSWORD = 'district'
TEST_DOMAIN = 'test-domain'


class RequestsTests(SimpleTestCase):

    def setUp(self):
        self.requests = get_basic_requests(
            TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD
        )
        self.org_unit_id = 'abc'
        self.data_element_id = '123'

    def test_send_data_value_set(self):
        with patch('corehq.motech.requests.RequestLog', Mock()), \
                patch.object(requests.Session, 'request') as request_mock:
            payload = {'dataValues': [
                {'dataElement': self.data_element_id, 'period': "201701",
                 'orgUnit': self.org_unit_id, 'value': "180"},
                {'dataElement': self.data_element_id, 'period': "201702",
                 'orgUnit': self.org_unit_id, 'value': "200"},
            ]}
            content = {'status': 'SUCCESS', 'importCount': {'imported': 2}}
            content_json = json.dumps(content)
            response_mock = Mock()
            response_mock.status_code = 201
            response_mock.content = content_json
            response_mock.json.return_value = content
            request_mock.return_value = response_mock

            response = self.requests.post('dataValueSets', json=payload)
            request_mock.assert_called_with(
                'POST',
                'http://localhost:9080/api/dataValueSets',
                data=None,
                json=payload,
                headers={'Content-type': 'application/json', 'Accept': 'application/json'},
                auth=(TEST_API_USERNAME, TEST_API_PASSWORD),
                timeout=REQUEST_TIMEOUT,
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()['status'], 'SUCCESS')
            self.assertEqual(response.json()['importCount']['imported'], 2)

    def test_verify_ssl(self):
        with patch('corehq.motech.requests.RequestLog', Mock()), \
                patch.object(requests.Session, 'request') as request_mock:

            self.requests = get_basic_requests(
                TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD,
                verify=False,
            )
            self.requests.get('me')
            request_mock.assert_called_with(
                'GET',
                TEST_API_URL + 'me',
                allow_redirects=True,
                headers={'Accept': 'application/json'},
                auth=(TEST_API_USERNAME, TEST_API_PASSWORD),
                timeout=REQUEST_TIMEOUT,
                verify=False
            )

    def test_with_session(self):
        with patch('corehq.motech.requests.RequestLog', Mock()), \
                patch.object(requests.Session, 'request'), \
                patch.object(requests.Session, 'close') as close_mock:

            with get_basic_requests(
                TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD
            ) as self.requests:
                self.requests.get('me')
                self.requests.get('me')
                self.requests.get('me')
            self.assertEqual(close_mock.call_count, 1)

    def test_without_session(self):
        with patch('corehq.motech.requests.RequestLog', Mock()), \
                patch.object(requests.Session, 'request'), \
                patch.object(requests.Session, 'close') as close_mock:

            self.requests.get('me')
            self.requests.get('me')
            self.requests.get('me')
            self.assertEqual(close_mock.call_count, 3)

    def test_with_and_without_session(self):
        with patch('corehq.motech.requests.RequestLog', Mock()), \
                patch.object(requests.Session, 'request'), \
                patch.object(requests.Session, 'close') as close_mock:

            with get_basic_requests(
                TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD
            ) as self.requests:
                self.requests.get('me')
                self.requests.get('me')
                self.requests.get('me')
            self.requests.get('me')
            self.assertEqual(close_mock.call_count, 2)

    def test_notify_error_no_address(self):
        with patch('corehq.motech.requests.send_mail_async') as send_mail_mock:
            self.requests.notify_error('foo')
            send_mail_mock.delay.assert_not_called()

    def test_notify_error_address_list(self):
        requests = get_basic_requests(
            TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD,
            notify_addresses=['foo@example.com', 'bar@example.com']
        )
        with patch('corehq.motech.requests.send_mail_async') as send_mail_mock:
            requests.notify_error('foo')
            send_mail_mock.delay.assert_called_with(
                'MOTECH Error',
                (
                    'foo\r\n'
                    'Project space: test-domain\r\n'
                    'Remote API base URL: http://localhost:9080/api/\r\n'
                    'Remote API username: admin'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['foo@example.com', 'bar@example.com']
            )


class RequestsAuthenticationTests(SimpleTestCase):

    def test_no_auth(self):
        auth_manager = AuthManager()
        reqs = Requests(TEST_DOMAIN, TEST_API_URL, auth_manager=auth_manager)
        with patch('corehq.motech.requests.RequestLog', Mock()), \
                patch.object(requests.Session, 'request') as request_mock:
            request_mock.return_value = self.get_response_mock()

            reqs.get('me')

            kwargs = request_mock.call_args[1]
            self.assertNotIn('auth', kwargs)

    def test_basic_auth(self):
        auth_manager = BasicAuthManager(TEST_API_USERNAME, TEST_API_PASSWORD)
        reqs = Requests(TEST_DOMAIN, TEST_API_URL, auth_manager=auth_manager)
        with patch('corehq.motech.requests.RequestLog', Mock()), \
                patch.object(requests.Session, 'request') as request_mock:
            request_mock.return_value = self.get_response_mock()

            reqs.get('me')

            kwargs = request_mock.call_args[1]
            self.assertEqual(kwargs['auth'], (TEST_API_USERNAME, TEST_API_PASSWORD))

    def test_digest_auth(self):
        auth_manager = DigestAuthManager(TEST_API_USERNAME, TEST_API_PASSWORD)
        reqs = Requests(TEST_DOMAIN, TEST_API_URL, auth_manager=auth_manager)
        with patch('corehq.motech.requests.RequestLog', Mock()), \
                patch.object(requests.Session, 'request') as request_mock:
            request_mock.return_value = self.get_response_mock()

            reqs.get('me')

            kwargs = request_mock.call_args[1]
            auth_class = kwargs['auth'].__class__.__name__
            self.assertEqual(auth_class, 'HTTPDigestAuth')

    def get_response_mock(self):
        content = {'code': TEST_API_USERNAME}
        content_json = json.dumps(content)
        response_mock = Mock()
        response_mock.status_code = 200
        response_mock.content = content_json
        response_mock.json.return_value = content
        return response_mock


@skip('This test uses third-party resources.')  # Comment this out to run
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
            TEST_DOMAIN, cls.base_url, cls.username, cls.password,
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
            TEST_DOMAIN, cls.base_url, cls.username, cls.password,
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
            TEST_DOMAIN,
            self.base_url,
            auth_manager=auth_manager,
        ) as requests:
            # NOTE: Use Requests instance as a context manager so that
            #       it uses OAuth2Session.
            resp = requests.get('/api/me/')

            # Check API request succeeded
            self.assertEqual(resp.json()['name'], self.fullname)

            # Check token
            expected_keys = {'access_token', 'expires_at', 'expires_in',
                             'refresh_token', 'scope', 'token_type'}
            self.assertEqual(set(requests.last_token), expected_keys)
            self.assertEqual(requests.last_token['token_type'], 'bearer')


def mkpasswd(length):
    population = ''.join((
        string.ascii_uppercase,
        string.ascii_lowercase,
        string.digits,
    ))
    return ''.join(random.choices(population, k=length))
