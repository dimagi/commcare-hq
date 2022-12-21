import json
import logging
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

import requests
from unittest.mock import Mock, patch

from corehq.apps.hqwebapp.templatetags.hq_shared_tags import pp_json
from corehq.motech.const import ALGO_AES, PASSWORD_PLACEHOLDER
from corehq.motech.models import (
    ConnectionSettings,
    RequestLog,
    RequestLogEntry,
)
from corehq.motech.requests import get_basic_requests
from corehq.util import as_json_text, as_text

TEST_API_URL = 'http://example.com:9080/api/'
TEST_API_USERNAME = 'admin'
TEST_API_PASSWORD = 'district'
TEST_DOMAIN = 'test-domain'


class UnpackRequestArgsTests(SimpleTestCase):

    def setUp(self):
        self.requests = get_basic_requests(
            TEST_DOMAIN,
            TEST_API_URL,
            TEST_API_USERNAME,
            TEST_API_PASSWORD,
        )

        content = {'status': 'Created'}
        self.content_json = json.dumps(content)
        self.request_method = 'POST'
        self.request_headers = {
            'Content-type': 'application/json',
            'Accept': 'application/json'
        }
        self.status_code = 201
        self.response_headers = {'Content-Type': 'application/json'}
        self.error_message = ''
        self.uri = 'person/'
        self.json_data = {'name': 'Alice'}
        self.data = json.dumps(self.json_data)

        self.response_mock = Mock()
        self.response_mock.status_code = self.status_code
        self.response_mock.content = self.content_json
        self.response_mock.headers = self.response_headers
        self.response_mock.json.return_value = content

        self.request_patcher = patch.object(requests.Session, 'request')
        self.request_mock = self.request_patcher.start()
        self.request_mock.return_value = self.response_mock

        self.create_patcher = patch.object(RequestLog.objects, 'create')
        self.create_mock = self.create_patcher.start()

    def tearDown(self):
        self.create_patcher.stop()
        self.request_patcher.stop()

    def assert_create_called_with_request_body_and_params(
        self, create_mock, request_body, request_params=None
    ):
        create_mock.assert_called_with(
            domain=TEST_DOMAIN,
            log_level=logging.INFO,
            payload_id=None,
            request_body=as_json_text(request_body),
            request_error=self.error_message,
            request_headers=self.request_headers,
            request_method=self.request_method,
            request_params=request_params,
            request_url=f'{TEST_API_URL}person/',
            response_body=as_text(self.content_json),
            response_status=self.status_code,
            response_headers=self.response_headers,
        )

    def test_post_with_no_args(self):
        self.requests.post(self.uri)
        self.assert_create_called_with_request_body_and_params(
            self.create_mock, None
        )

    def test_post_with_data_kwarg(self):
        self.requests.post(self.uri, data=self.data)
        self.assert_create_called_with_request_body_and_params(
            self.create_mock, self.data
        )

    def test_post_with_json_kwarg(self):
        self.requests.post(self.uri, json=self.json_data)
        self.assert_create_called_with_request_body_and_params(
            self.create_mock, self.json_data
        )

    def test_post_with_data_arg(self):
        self.requests.post(self.uri, self.data)
        self.assert_create_called_with_request_body_and_params(
            self.create_mock, self.data
        )

    def test_post_with_json_arg(self):
        self.requests.post(self.uri, None, self.json_data)
        self.assert_create_called_with_request_body_and_params(
            self.create_mock, self.json_data
        )

    def test_post_with_data_and_json(self):
        self.requests.post(self.uri, self.data, self.json_data)
        self.assert_create_called_with_request_body_and_params(
            self.create_mock, self.data
        )

    def test_get_with_params(self):
        content = {'code': TEST_API_USERNAME}
        self.content_json = json.dumps(content)
        self.request_method = 'GET'
        request_params = {'v': 'full'}
        self.request_headers = {'Accept': 'application/json'}
        self.status_code = 200
        self.response_mock.status_code = self.status_code
        self.response_mock.content = self.content_json
        self.response_mock.json.return_value = content

        self.requests.get(self.uri, request_params)
        self.assert_create_called_with_request_body_and_params(
            self.create_mock, None, request_params
        )

    def test_delete(self):
        content = {'status': 'Deleted'}
        self.content_json = json.dumps(content)
        self.request_method = 'DELETE'
        self.request_headers = {'Accept': 'application/json'}
        self.status_code = 200
        self.response_mock.status_code = self.status_code
        self.response_mock.content = self.content_json
        self.response_mock.json.return_value = content

        self.requests.delete(self.uri)
        self.assert_create_called_with_request_body_and_params(
            self.create_mock, None
        )


class ConnectionSettingsPropertiesTests(SimpleTestCase):

    def test_password_placeholder(self):
        cs = ConnectionSettings()
        cs.plaintext_password = PASSWORD_PLACEHOLDER
        self.assertEqual(cs.password, '')

    def test_client_secret_placeholder(self):
        cs = ConnectionSettings()
        cs.plaintext_client_secret = PASSWORD_PLACEHOLDER
        self.assertEqual(cs.client_secret, '')

    def test_password_setter(self):
        cs = ConnectionSettings()
        cs.plaintext_password = 'secret'
        self.assertTrue(cs.password.startswith(f'${ALGO_AES}$'))

    def test_client_secret_setter(self):
        cs = ConnectionSettings()
        cs.plaintext_client_secret = 'secret'
        self.assertTrue(cs.client_secret.startswith(f'${ALGO_AES}$'))

    def test_password_getter_decrypts(self):
        cs = ConnectionSettings()
        cs.plaintext_password = 'secret'
        self.assertEqual(cs.plaintext_password, 'secret')

    def test_client_secret_getter_decrypts(self):
        cs = ConnectionSettings()
        cs.plaintext_client_secret = 'secret'
        self.assertEqual(cs.plaintext_client_secret, 'secret')

    def test_password_getter_returns(self):
        cs = ConnectionSettings()
        cs.password = 'secret'
        self.assertEqual(cs.plaintext_password, 'secret')

    def test_client_secret_getter_returns(self):
        cs = ConnectionSettings()
        cs.client_secret = 'secret'
        self.assertEqual(cs.plaintext_client_secret, 'secret')


class NotifyAddressesTests(SimpleTestCase):

    def test_default(self):
        cs = ConnectionSettings()
        self.assertEqual(cs.notify_addresses, [])

    def test_empty(self):
        cs = ConnectionSettings()
        cs.notify_addresses_str = ""
        self.assertEqual(cs.notify_addresses, [])

    def test_one(self):
        cs = ConnectionSettings()
        cs.notify_addresses_str = "admin@example.com"
        self.assertEqual(cs.notify_addresses, ["admin@example.com"])

    def test_comma(self):
        cs = ConnectionSettings()
        cs.notify_addresses_str = "admin@example.com,user@example.com"
        self.assertEqual(cs.notify_addresses, ["admin@example.com",
                                               "user@example.com"])

    def test_space(self):
        cs = ConnectionSettings()
        cs.notify_addresses_str = "admin@example.com user@example.com"
        self.assertEqual(cs.notify_addresses, ["admin@example.com",
                                               "user@example.com"])

    def test_commaspace(self):
        cs = ConnectionSettings()
        cs.notify_addresses_str = "admin@example.com, user@example.com"
        self.assertEqual(cs.notify_addresses, ["admin@example.com",
                                               "user@example.com"])

    def test_mess(self):
        cs = ConnectionSettings()
        cs.notify_addresses_str = "admin@example.com,,, ,  user@example.com"
        self.assertEqual(cs.notify_addresses, ["admin@example.com",
                                               "user@example.com"])


class TestRequestLogFormatting(TestCase):
    """
    Tests the formatting of the value that shows up in the RequestLog
    details page.
    """

    def test_request_body_dict(self):
        entry = self.get_entry(request_body={'hello': 'world!'})
        request_log = RequestLog.log(level=logging.DEBUG, log_entry=entry)
        template_value = pp_json(request_log.request_body)
        self.assertEqual(template_value, '{\n  "hello": "world!"\n}')

    def test_request_body_str(self):
        entry = self.get_entry(request_body='hello, world!')
        request_log = RequestLog.log(level=logging.DEBUG, log_entry=entry)
        template_value = pp_json(request_log.request_body)
        self.assertEqual(template_value, 'hello, world!')

    def test_request_body_unserializable(self):
        entry = self.get_entry(request_body={'hello': Decimal('1.0')})
        request_log = RequestLog.log(level=logging.DEBUG, log_entry=entry)
        template_value = pp_json(request_log.request_body)
        self.assertEqual(template_value, "{'hello': Decimal('1.0')}")

    def test_request_body_none(self):
        entry = self.get_entry(request_body=None)
        request_log = RequestLog.log(level=logging.DEBUG, log_entry=entry)
        template_value = pp_json(request_log.request_body)
        self.assertEqual(template_value, '')

    @staticmethod
    def get_entry(request_body):
        return RequestLogEntry(
            domain=TEST_DOMAIN,
            payload_id='c0ffee',
            method='POST',
            url='https://example.com/api/',
            headers={},
            params={},
            data=request_body,
            error='',
            response_status=200,
            response_headers={},
            response_body='OK',
        )
