from __future__ import absolute_import
from __future__ import unicode_literals
import json
from django.test import SimpleTestCase
from mock import patch, Mock
from corehq.motech.dhis2.api import JsonApiRequest


TEST_API_URL = 'http://localhost:9080/api/'
TEST_API_USERNAME = 'admin'
TEST_API_PASSWORD = 'district'
TEST_DOMAIN = 'test-domain'


class JsonApiRequestTests(SimpleTestCase):

    def setUp(self):
        patcher = patch('corehq.motech.dhis2.api.get_dhis2_connection')
        get_dhis2_connection_mock = patcher.start()
        get_dhis2_connection_mock.return_value = Mock(log_level=99)  # Don't log anything
        self.addCleanup(patcher.stop)

        self.api = JsonApiRequest(TEST_DOMAIN, TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD)
        self.org_unit_id = 'abc'
        self.data_element_id = '123'

    def test_authentication(self):
        with patch('corehq.motech.dhis2.api.requests') as requests_mock:
            content = {'code': TEST_API_USERNAME}
            content_json = json.dumps(content)
            response_mock = Mock()
            response_mock.status_code = 200
            response_mock.content = content_json
            response_mock.json.return_value = content
            requests_mock.get.return_value = response_mock

            response = self.api.get('me')
            requests_mock.get.assert_called_with(
                TEST_API_URL + 'me',
                headers={'Accept': 'application/json'},
                auth=(TEST_API_USERNAME, TEST_API_PASSWORD)
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['code'], TEST_API_USERNAME)

    def test_send_data_value_set(self):
        with patch('corehq.motech.dhis2.api.requests') as requests_mock:
            payload = {'dataValues': [
                {'dataElement': self.data_element_id, 'period': "201701",
                 'orgUnit': self.org_unit_id, 'value': "180"},
                {'dataElement': self.data_element_id, 'period': "201702",
                 'orgUnit': self.org_unit_id, 'value': "200"},
            ]}
            payload_json = json.dumps(payload)
            content = {'status': 'SUCCESS', 'importCount': {'imported': 2}}
            content_json = json.dumps(content)
            response_mock = Mock()
            response_mock.status_code = 201
            response_mock.content = content_json
            response_mock.json.return_value = content
            requests_mock.post.return_value = response_mock

            response = self.api.post('dataValueSets', payload)
            requests_mock.post.assert_called_with(
                'http://localhost:9080/api/dataValueSets',
                payload_json,
                headers={'Content-type': 'application/json', 'Accept': 'application/json'},
                auth=(TEST_API_USERNAME, TEST_API_PASSWORD)
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()['status'], 'SUCCESS')
            self.assertEqual(response.json()['importCount']['imported'], 2)
