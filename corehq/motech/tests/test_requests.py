import json

from django.conf import settings
from django.test import SimpleTestCase

import requests
from mock import Mock, patch

from corehq.motech.const import REQUEST_TIMEOUT
from corehq.motech.requests import Requests

TEST_API_URL = 'http://localhost:9080/api/'
TEST_API_USERNAME = 'admin'
TEST_API_PASSWORD = 'district'
TEST_DOMAIN = 'test-domain'

def noop_logger(*args, **kwargs):
    pass


class RequestsTests(SimpleTestCase):

    def setUp(self):
        self.requests = Requests(
            TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD, logger=noop_logger
        )
        self.org_unit_id = 'abc'
        self.data_element_id = '123'

    def test_authentication(self):
        with patch.object(requests.Session, 'request') as request_mock:
            content = {'code': TEST_API_USERNAME}
            content_json = json.dumps(content)
            response_mock = Mock()
            response_mock.status_code = 200
            response_mock.content = content_json
            response_mock.json.return_value = content
            request_mock.return_value = response_mock

            response = self.requests.get('me')
            request_mock.assert_called_with(
                'GET',
                TEST_API_URL + 'me',
                allow_redirects=True,
                headers={'Accept': 'application/json'},
                auth=(TEST_API_USERNAME, TEST_API_PASSWORD),
                timeout=REQUEST_TIMEOUT,
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['code'], TEST_API_USERNAME)

    def test_send_data_value_set(self):
        with patch.object(requests.Session, 'request') as request_mock:
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
        with patch.object(requests.Session, 'request') as request_mock:

            req = Requests(TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD, verify=False,
                           logger=noop_logger)
            req.get('me')
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
        with patch.object(requests.Session, 'request'), \
                patch.object(requests.Session, 'close') as close_mock:

            request = Requests(TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD,
                               logger=noop_logger)
            with request as req:
                req.get('me')
                req.get('me')
                req.get('me')
            self.assertEqual(close_mock.call_count, 1)

    def test_without_session(self):
        with patch.object(requests.Session, 'request'), \
                patch.object(requests.Session, 'close') as close_mock:

            self.requests.get('me')
            self.requests.get('me')
            self.requests.get('me')
            self.assertEqual(close_mock.call_count, 3)

    def test_with_and_without_session(self):
        with patch.object(requests.Session, 'request'), \
                patch.object(requests.Session, 'close') as close_mock:

            request = Requests(TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD,
                               logger=noop_logger)
            with request as req:
                req.get('me')
                req.get('me')
                req.get('me')
            req.get('me')
            self.assertEqual(close_mock.call_count, 2)

    def test_notify_error_no_address(self):
        with patch('corehq.motech.requests.send_mail_async') as send_mail_mock:
            self.requests.notify_error('foo')
            send_mail_mock.delay.assert_not_called()

    def test_notify_error_address_list(self):
        requests = Requests(TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD,
                            notify_addresses=['foo@example.com', 'bar@example.com'])
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
