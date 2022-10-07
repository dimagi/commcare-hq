import json
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.const import UCR_NAMED_EXPRESSION
from corehq.apps.userreports.models import UCRExpression
from corehq.apps.users.models import HQApiKey, WebUser
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.motech.generic_inbound.models import (
    ConfigurableAPI,
    ProcessingAttempt,
    RequestLog,
)


class TestGenericInboundAPIView(TestCase):
    domain_name = 'ucr-api-test'
    example_post_data = {'name': 'cricket', 'is_team_sport': True}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.user = WebUser.create(cls.domain_name, 'test@dimagi.com', 'secret', None, None)
        cls.addClassCleanup(cls.domain.delete)

        cls.api_key, _ = HQApiKey.objects.get_or_create(user=cls.user.get_django_user())

    def _make_api(self, property_expressions):
        return ConfigurableAPI.objects.create(
            domain=self.domain_name,
            transform_expression=self._make_expression(property_expressions)
        )

    def _make_expression(self, property_expressions):
        return UCRExpression.objects.create(
            name='create_sport',
            domain=self.domain_name,
            expression_type=UCR_NAMED_EXPRESSION,
            definition=self._get_ucr_case_expression(property_expressions)
        )

    def _get_ucr_case_expression(self, property_expressions):
        return {
            'type': 'dict',
            'properties': {
                'create': True,
                'case_type': 'sport',
                'case_name': {
                    'type': 'jsonpath',
                    'jsonpath': 'body.name',
                },
                'owner_id': {
                    'type': 'jsonpath',
                    'jsonpath': 'user.uuid'
                },
                'properties': {
                    'type': 'dict',
                    'properties': property_expressions
                }
            }
        }

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain_name)
        super().tearDownClass()

    def test_post_denied(self):
        generic_api = self._make_api({})
        url = reverse('generic_inbound_api', args=[self.domain_name, generic_api.url_key])
        response = self.client.post(url, data={})
        self.assertEqual(response.status_code, 401)

    def test_post_not_json(self):
        generic_api = self._make_api({})
        url = reverse('generic_inbound_api', args=[self.domain_name, generic_api.url_key])
        response = self.client.post(
            url, data={}, HTTP_AUTHORIZATION=f"apikey {self.user.username}:{self.api_key.key}"
        )
        self.assertEqual(response.status_code, 400)

    def test_post(self):
        response_json = self._test_generic_api({
            'is_team_sport': {
                'type': 'jsonpath',
                'jsonpath': 'body.is_team_sport',
                'datatype': 'string',
            }
        })
        self.assertEqual(response_json['cases'][0]['properties']['is_team_sport'], 'True')

    def test_post_with_query(self):
        query_params = {"param": "value"}
        properties_expression = {
            'prop_from_query': {
                'type': 'jsonpath',
                'jsonpath': 'request.query.param[0]',
            }
        }
        response_json = self._test_generic_api(properties_expression, query_params)
        self.assertEqual(response_json['cases'][0]['properties']['prop_from_query'], 'value')

    def _test_generic_api(self, properties_expression, query_params=None):
        generic_api = self._make_api(properties_expression)
        url = reverse('generic_inbound_api', args=[self.domain_name, generic_api.url_key])
        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        data = json.dumps(self.example_post_data)
        response = self.client.post(
            url, data=data, content_type="application/json",
            HTTP_AUTHORIZATION=f"apikey {self.user.username}:{self.api_key.key}",
            HTTP_USER_AGENT="user agent string",
        )
        response_json = response.json()
        self.assertEqual(response.status_code, 200, response_json)
        self.assertItemsEqual(response_json.keys(), ['cases', 'form_id'])
        self.assertEqual(response_json['cases'][0]['owner_id'], self.user.get_id)
        return response_json

    def test_logging(self):
        query_params = {"param": "value"}
        properties_expression = {
            'prop_from_query': {
                'type': 'jsonpath',
                'jsonpath': 'request.query.param[0]',
            }
        }
        response_json = self._test_generic_api(properties_expression, query_params)

        log = RequestLog.objects.last()
        self.assertEqual(log.domain, self.domain_name)
        self.assertIsInstance(log.api, ConfigurableAPI)
        self.assertEqual(log.status, RequestLog.Status.SUCCESS)
        self.assertEqual(log.attempts, 1)
        self.assertEqual(log.response_status, 200)
        self.assertEqual(log.error_message, '')
        self.assertEqual(log.username, self.user.username)
        self.assertEqual(log.request_method, RequestLog.RequestMethod.POST)
        self.assertEqual(log.request_query, 'param=value')
        self.assertEqual(log.request_body, json.dumps(self.example_post_data))
        self.assertIn('CONTENT_TYPE', log.request_headers)
        self.assertEqual(log.request_headers['HTTP_USER_AGENT'], 'user agent string')
        self.assertEqual(log.request_ip, '127.0.0.1')

        attempt = ProcessingAttempt.objects.last()
        self.assertEqual(attempt.is_retry, False)
        self.assertEqual(attempt.response_status, 200)
        self.assertEqual(json.loads(attempt.response_body), response_json)
        self.assertEqual(attempt.raw_response, response_json)
        self.assertEqual(attempt.xform_id, response_json.get('form_id'))
        self.assertEqual(attempt.case_ids, [response_json.get('cases')[0]['case_id']])
