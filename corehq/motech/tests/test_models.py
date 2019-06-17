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


class UnpackRequestArgsTests(SimpleTestCase):

    def setUp(self):
        self.requests = Requests(TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD)

        content = {'status': 'Created'}
        self.content_json = json.dumps(content)
        self.request_method = 'POST'
        self.request_headers = {
            'Content-type': 'application/json',
            'Accept': 'application/json'
        }
        self.status_code = 201
        self.error_message = ''
        self.uri = 'person/'
        self.json_data = {'name': 'Alice'}
        self.data = json.dumps(self.json_data)

        self.response_mock = Mock()
        self.response_mock.status_code = self.status_code
        self.response_mock.content = self.content_json
        self.response_mock.json.return_value = content

    def assert_create_called_with_request_body_and_params(self, create_mock, request_body, request_params=None):
            create_mock.assert_called_with(
                domain=TEST_DOMAIN,
                log_level=logging.INFO,
                request_body=request_body,
                request_error=self.error_message,
                request_headers=self.request_headers,
                request_method=self.request_method,
                request_params=request_params,
                request_url='http://localhost:9080/api/person/',
                response_body=self.content_json,
                response_status=self.status_code,
            )

    def test_post_with_no_args(self):
        with patch.object(requests.Session, 'request') as request_mock, \
                patch.object(RequestLog.objects, 'create') as create_mock:
            request_mock.return_value = self.response_mock

            self.requests.post(self.uri)
            self.assert_create_called_with_request_body_and_params(create_mock, None)

    def test_post_with_data_kwarg(self):
        with patch.object(requests.Session, 'request') as request_mock, \
                patch.object(RequestLog.objects, 'create') as create_mock:
            request_mock.return_value = self.response_mock

            self.requests.post(self.uri, data=self.data)
            self.assert_create_called_with_request_body_and_params(create_mock, self.data)

    def test_post_with_json_kwarg(self):
        with patch.object(requests.Session, 'request') as request_mock, \
                patch.object(RequestLog.objects, 'create') as create_mock:
            request_mock.return_value = self.response_mock

            self.requests.post(self.uri, json=self.json_data)
            self.assert_create_called_with_request_body_and_params(create_mock, self.json_data)

    def test_post_with_data_arg(self):
        with patch.object(requests.Session, 'request') as request_mock, \
                patch.object(RequestLog.objects, 'create') as create_mock:
            request_mock.return_value = self.response_mock

            self.requests.post(self.uri, self.data)
            self.assert_create_called_with_request_body_and_params(create_mock, self.data)

    def test_post_with_json_arg(self):
        with patch.object(requests.Session, 'request') as request_mock, \
                patch.object(RequestLog.objects, 'create') as create_mock:
            request_mock.return_value = self.response_mock

            self.requests.post(self.uri, None, self.json_data)
            self.assert_create_called_with_request_body_and_params(create_mock, self.json_data)

    def test_post_with_data_and_json(self):
        with patch.object(requests.Session, 'request') as request_mock, \
                patch.object(RequestLog.objects, 'create') as create_mock:
            request_mock.return_value = self.response_mock

            self.requests.post(self.uri, self.data, self.json_data)
            self.assert_create_called_with_request_body_and_params(create_mock, self.data)

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

        with patch.object(requests.Session, 'request') as request_mock, \
                patch.object(RequestLog.objects, 'create') as create_mock:
            request_mock.return_value = self.response_mock

            self.requests.get(self.uri, request_params)
            self.assert_create_called_with_request_body_and_params(create_mock, None, request_params)

    def test_delete(self):
        content = {'status': 'Deleted'}
        self.content_json = json.dumps(content)
        self.request_method = 'DELETE'
        self.request_headers = {'Accept': 'application/json'}
        self.status_code = 200
        self.response_mock.status_code = self.status_code
        self.response_mock.content = self.content_json
        self.response_mock.json.return_value = content

        with patch.object(requests.Session, 'request') as request_mock, \
                patch.object(RequestLog.objects, 'create') as create_mock:
            request_mock.return_value = self.response_mock

            self.requests.delete(self.uri)
            self.assert_create_called_with_request_body_and_params(create_mock, None)
