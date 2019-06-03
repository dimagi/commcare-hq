from __future__ import absolute_import, unicode_literals

import json
import logging

from django.test import SimpleTestCase

import requests
from mock import patch, Mock

from corehq.motech.models import RequestLog
from corehq.motech.requests import Requests

TEST_API_URL = 'http://localhost:9080/api/'
TEST_API_USERNAME = 'admin'
TEST_API_PASSWORD = 'district'
TEST_DOMAIN = 'test-domain'


class RequestLogTests(SimpleTestCase):

    def setUp(self):
        self.requests = Requests(TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD)

    def test_get_request_log(self):
        with patch.object(requests.Session, 'request') as request_mock, \
                patch.object(RequestLog, 'log') as log_mock:

            content = {'code': TEST_API_USERNAME}
            content_json = json.dumps(content)
            status_code = 200
            error_message = ''
            uri = 'me'
            response_mock = Mock()
            response_mock.status_code = status_code
            response_mock.content = content_json
            response_mock.json.return_value = content
            request_mock.return_value = response_mock

            self.requests.get(uri)

            log_mock.assert_called_with(
                logging.INFO,
                TEST_DOMAIN,
                error_message,
                status_code,
                content_json,
                'GET',
                TEST_API_URL + uri,
                allow_redirects=True,
                auth=(TEST_API_USERNAME, TEST_API_PASSWORD),
                headers={'Accept': 'application/json'},
            )

    def test_delete_request_log(self):
        with patch.object(requests.Session, 'request') as request_mock, \
                patch.object(RequestLog, 'log') as log_mock:

            content = {'status': 'Deleted'}
            content_json = json.dumps(content)
            status_code = 200
            error_message = ''
            uri = 'person/123'
            response_mock = Mock()
            response_mock.status_code = status_code
            response_mock.content = content_json
            response_mock.json.return_value = content
            request_mock.return_value = response_mock

            self.requests.delete(uri)

            log_mock.assert_called_with(
                logging.INFO,
                TEST_DOMAIN,
                error_message,
                status_code,
                content_json,
                'DELETE',
                TEST_API_URL + uri,
                auth=(TEST_API_USERNAME, TEST_API_PASSWORD),
                headers={'Accept': 'application/json'},
            )

    def test_post_request_log(self):
        with patch.object(requests.Session, 'request') as request_mock, \
                patch.object(RequestLog, 'log') as log_mock:

            content = {'status': 'Created'}
            content_json = json.dumps(content)
            status_code = 201
            error_message = ''
            uri = 'person/'
            response_mock = Mock()
            response_mock.status_code = status_code
            response_mock.content = content_json
            response_mock.json.return_value = content
            request_mock.return_value = response_mock

            self.requests.post(uri, json={'name': 'Alice'})

            log_mock.assert_called_with(
                logging.INFO,
                TEST_DOMAIN,
                error_message,
                status_code,
                content_json,
                'POST',
                TEST_API_URL + uri,
                auth=(TEST_API_USERNAME, TEST_API_PASSWORD),
                data=None,
                headers={
                    'Content-type': 'application/json',
                    'Accept': 'application/json',
                },
                json={'name': 'Alice'},
            )
