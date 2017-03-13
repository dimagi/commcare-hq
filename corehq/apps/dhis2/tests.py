import json
from django.test import SimpleTestCase
from mock import patch, Mock
from corehq.apps.dhis2.models import JsonApiRequest


TEST_API_URL = 'http://localhost:9080/api/'
TEST_API_USERNAME = 'admin'
TEST_API_PASSWORD = 'district'


class JsonApiRequestTests(SimpleTestCase):

    def setUp(self):
        self.api = JsonApiRequest(TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD)
        self.org_unit_id = 'abc'
        self.data_element_id = '123'

    def test_authentication(self):
        with patch('corehq.apps.dhis2.models.requests') as requests_mock:
            content = {'code': TEST_API_USERNAME}
            content_json = json.dumps(content)
            response_mock = Mock()
            response_mock.status_code = 200
            response_mock.content = content_json
            response_mock.json.return_value = content
            requests_mock.get.return_value = response_mock

            me = self.api.get('me')
            requests_mock.get.assert_called_with(
                TEST_API_URL + 'me',
                headers={'Accept': 'application/json'},
                auth=(TEST_API_USERNAME, TEST_API_PASSWORD)
            )
            self.assertEqual(me['code'], TEST_API_USERNAME)

    def test_send_data_value_set(self):
        with patch('corehq.apps.dhis2.models.requests') as requests_mock:
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
            self.assertEqual(response['status'], 'SUCCESS')
            self.assertEqual(response['importCount']['imported'], 2)
