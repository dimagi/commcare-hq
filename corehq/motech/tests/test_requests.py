from __future__ import absolute_import, unicode_literals

import json

from django.test import SimpleTestCase

import requests
from mock import Mock, patch

from corehq.motech.requests import Requests


TEST_API_URL = 'http://localhost:9080/api/'
TEST_API_USERNAME = 'admin'
TEST_API_PASSWORD = 'district'
TEST_DOMAIN = 'test-domain'


class RequestsTests(SimpleTestCase):

    def setUp(self):
        self.requests = Requests(TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD)
        self.org_unit_id = 'abc'
        self.data_element_id = '123'

    def test_authentication(self):
        with patch('corehq.motech.requests.RequestLog', Mock()), \
                patch.object(requests.Session, 'request') as request_mock:
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
                timeout=600,
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['code'], TEST_API_USERNAME)

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
                timeout=600,
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()['status'], 'SUCCESS')
            self.assertEqual(response.json()['importCount']['imported'], 2)

    def test_verify_ssl(self):
        with patch('corehq.motech.requests.RequestLog', Mock()), \
                patch.object(requests.Session, 'request') as request_mock:

            self.requests = Requests(TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD, verify=False)
            self.requests.get('me')
            request_mock.assert_called_with(
                'GET',
                TEST_API_URL + 'me',
                allow_redirects=True,
                headers={'Accept': 'application/json'},
                auth=(TEST_API_USERNAME, TEST_API_PASSWORD),
                timeout=600,
                verify=False
            )

    def test_with_session(self):
        with patch('corehq.motech.requests.RequestLog', Mock()), \
                patch.object(requests.Session, 'request'), \
                patch.object(requests.Session, 'close') as close_mock:

            with Requests(TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD) as self.requests:
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

            with Requests(TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD) as self.requests:
                self.requests.get('me')
                self.requests.get('me')
                self.requests.get('me')
            self.requests.get('me')
            self.assertEqual(close_mock.call_count, 2)
