import json
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse

import attrs

from django.conf import settings
from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.const import (
    UCR_NAMED_EXPRESSION,
    UCR_NAMED_FILTER,
)
from corehq.apps.userreports.models import UCRExpression
from corehq.apps.users.models import HQApiKey, WebUser
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.motech.generic_inbound.models import (
    ConfigurableAPI,
    ConfigurableApiValidation,
    ProcessingAttempt,
    RequestLog, ApiBackendOptions,
)
from corehq.motech.generic_inbound.utils import (
    ApiRequest,
    archive_api_request,
    reprocess_api_request,
    revert_api_request_from_form,
)
from corehq.util.test_utils import flag_enabled, privilege_enabled
from corehq.form_processor.tests.utils import create_case


class GenericInboundAPIViewBaseTest(TestCase):
    domain_name = 'ucr-api-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.user = WebUser.create(cls.domain_name, 'test@dimagi.com', 'secret', None, None, is_admin=True)
        cls.addClassCleanup(cls.domain.delete)

        cls.api_key, _ = HQApiKey.objects.get_or_create(user=cls.user.get_django_user())

    def _make_api(self, property_expressions, filter_expression=None, validation_expression=None,
                  backend=ApiBackendOptions.json):
        api = ConfigurableAPI.objects.create(
            domain=self.domain_name,
            filter_expression=self._make_filter(filter_expression),
            transform_expression=self._make_expression(property_expressions),
            backend=backend,
        )

        if validation_expression:
            ConfigurableApiValidation.objects.create(
                api=api,
                name="test validation",
                expression=self._make_filter(validation_expression),
                message="Invalid request"
            )
        return api

    def _make_expression(self, property_expressions):
        return UCRExpression.objects.create(
            name='create_sport',
            domain=self.domain_name,
            expression_type=UCR_NAMED_EXPRESSION,
            definition=self._get_ucr_case_expression(property_expressions)
        )

    def _make_filter(self, filter_expression):
        if not filter_expression:
            return
        return UCRExpression.objects.create(
            name='api_filter',
            domain=self.domain_name,
            expression_type=UCR_NAMED_FILTER,
            definition=filter_expression
        )

    def _get_ucr_case_expression(self, property_expressions):
        return {
            'type': 'dict',
            'properties': {
                'create': True,
                'case_type': 'test-generic-inbound',
                'case_name': 'test inbound api',
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

    def _call_api(
        self,
        properties_expression,
        query_params=None,
        filter_expression=None,
        validation_expression=None,
        backend=ApiBackendOptions.json,
    ):
        generic_api = self._make_api(
            properties_expression, filter_expression, validation_expression, backend
        )
        return self._call_api_advanced(generic_api, query_params)

    def _call_api_advanced(self, api, query_params=None):
        url = reverse('generic_inbound_api', args=[self.domain_name, api.url_key])
        if query_params:
            url = f"{url}?{urlencode(query_params)}"
        data, content_type = self._get_post_data()
        response = self.client.post(
            url, data=data, content_type=content_type,
            HTTP_AUTHORIZATION=f"apikey {self.user.username}:{self.api_key.plaintext_key}",
            HTTP_USER_AGENT="user agent string",
        )
        return response

    def _get_post_data(self):
        """Return request POST data as a tuple(data, content_type)"""
        raise NotImplementedError

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain_name)
        super().tearDownClass()


@privilege_enabled(privileges.API_ACCESS)
@flag_enabled('API_THROTTLE_WHITELIST')
class TestGenericInboundAPIView(GenericInboundAPIViewBaseTest):
    additional_post_data = {}

    def _get_post_data(self):
        return (
            json.dumps({'name': 'cricket', 'is_team_sport': True, **self.additional_post_data}),
            "application/json"
        )

    def test_post_denied(self):
        generic_api = self._make_api({})
        url = reverse('generic_inbound_api', args=[self.domain_name, generic_api.url_key])
        response = self.client.post(url, data={})
        self.assertEqual(response.status_code, 401)

    def test_post_not_supported_type(self):
        generic_api = self._make_api({})
        url = reverse('generic_inbound_api', args=[self.domain_name, generic_api.url_key])
        response = self.client.post(
            url, data={}, HTTP_AUTHORIZATION=f"apikey {self.user.username}:{self.api_key.plaintext_key}"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Payload must be valid JSON"})

    def test_post_results_in_bad_type(self):
        expression = UCRExpression.objects.create(
            name="bad type",
            domain=self.domain_name,
            expression_type=UCR_NAMED_EXPRESSION,
            definition={"type": "property_name", "property_name": "name"}
        )
        api = ConfigurableAPI.objects.create(
            domain=self.domain_name,
            transform_expression=expression
        )
        response = self._call_api_advanced(api)
        self.assertEqual(response.status_code, 500, response.content)
        self.assertEqual(response.json(), {"error": "Unexpected type for transformed request"})

    def test_post_body_too_large(self):
        data_51_mb = "a" * (settings.MAX_UPLOAD_SIZE + 1)
        generic_api = self._make_api({})
        url = reverse('generic_inbound_api', args=[self.domain_name, generic_api.url_key])
        response = self.client.post(
            url, data=data_51_mb, HTTP_AUTHORIZATION=f"apikey {self.user.username}:{self.api_key.plaintext_key}",
            content_type="text"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Request exceeds the allowed size limit"})

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
        response = self._call_api(properties_expression, query_params)
        self.assertEqual(response.status_code, 200, response.content)
        response_json = response.json()
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
        self.assertEqual(log.username, self.user.username)
        self.assertEqual(log.request_method, RequestLog.RequestMethod.POST)
        self.assertEqual(log.request_query, 'param=value')
        self.assertEqual(log.request_body, self._get_post_data()[0])
        self.assertIn('CONTENT_TYPE', log.request_headers)
        self.assertEqual(log.request_headers['HTTP_USER_AGENT'], 'user agent string')
        self.assertEqual(log.request_ip, '127.0.0.1')

        attempt = ProcessingAttempt.objects.last()
        self.assertEqual(attempt.is_retry, False)
        self.assertEqual(attempt.response_status, 200)
        self.assertEqual(attempt.raw_response, response_json)
        self.assertEqual(json.loads(attempt.external_response), response_json)
        self.assertEqual(attempt.xform_id, response_json.get('form_id'))
        self.assertEqual(attempt.case_ids, [response_json.get('cases')[0]['case_id']])

    def test_logging_filtered_request(self):
        query_params = {"is_test": "1"}
        properties_expression = {'prop': 'const'}
        filter_expression = {
            "type": "boolean_expression",
            "operator": "eq",
            "expression": {
                "type": "jsonpath",
                "jsonpath": "request.query.is_test"
            },
            "property_value": None
        }
        response = self._call_api(properties_expression, query_params, filter_expression)

        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(response.content, b'')

        log = RequestLog.objects.last()
        self.assertEqual(log.domain, self.domain_name)
        self.assertEqual(log.status, RequestLog.Status.FILTERED)
        self.assertEqual(log.attempts, 1)
        self.assertEqual(log.response_status, 204)

        attempt = ProcessingAttempt.objects.last()
        self.assertEqual(attempt.is_retry, False)
        self.assertEqual(attempt.response_status, 204)

    def test_logging_validated_request(self):
        properties_expression = {'prop': 'const'}
        validation_expression = {
            "type": "boolean_expression",
            "operator": "in",
            "expression": {
                "type": "jsonpath",
                "jsonpath": "body.name"
            },
            "property_value": ["tennis", "hockey"]
        }
        response = self._call_api(properties_expression, validation_expression=validation_expression)

        self.assertEqual(response.status_code, 400, response.content)
        response_json = response.json()
        self.assertEqual(response_json['error'], 'validation error')

        log = RequestLog.objects.last()
        self.assertEqual(log.domain, self.domain_name)
        self.assertEqual(log.status, RequestLog.Status.VALIDATION_FAILED)
        self.assertEqual(log.attempts, 1)
        self.assertEqual(log.response_status, 400)

        attempt = ProcessingAttempt.objects.last()
        self.assertEqual(attempt.is_retry, False)
        self.assertEqual(attempt.response_status, 400)

    def test_request_data(self):
        query_params = {"param": "value"}
        properties_expression = {
            'prop_from_query': {
                'type': 'jsonpath',
                'jsonpath': 'request.query.param[0]',
            }
        }
        request = self._call_api(properties_expression, query_params).wsgi_request
        log = RequestLog.objects.last()

        original_data = ApiRequest.from_request(request, request_id=log.id)
        log_data = ApiRequest.from_log(log)

        for k, original_value in attrs.asdict(original_data).items():
            log_value = getattr(log_data, k)
            if k == 'couch_user':
                self.assertEqual(original_value.username, log_value.username)
            else:
                self.assertEqual(original_value, log_value)

    def test_retry(self):
        properties_expression = {'prop': 'const'}
        validation_expression = {
            "type": "boolean_expression",
            "operator": "in",
            "expression": {
                "type": "jsonpath",
                "jsonpath": "body.name"
            },
            "property_value": ["tennis", "hockey"]
        }
        response = self._call_api(properties_expression, validation_expression=validation_expression)
        self.assertEqual(response.status_code, 400, response.content)

        log = RequestLog.objects.last()
        self.assertEqual(log.status, RequestLog.Status.VALIDATION_FAILED)
        self.assertEqual(log.attempts, 1)

        # Delete the validation condition that caused it to fail
        api = ConfigurableAPI.objects.last()
        api.validations.all().delete()

        reprocess_api_request(log)
        log.refresh_from_db()
        self.assertEqual(log.status, RequestLog.Status.SUCCESS)
        self.assertEqual(log.attempts, 2)
        self.assertEqual(log.processingattempt_set.count(), 2)

        attempt = log.processingattempt_set.last()
        self.assertEqual(attempt.is_retry, True)
        self.assertEqual(attempt.response_status, 200)

    def test_retry_bad_json(self):
        api = self._make_api({'prop': 'const'})
        response = self.client.post(
            reverse('generic_inbound_api', args=[self.domain_name, api.url_key]),
            data='This is not JSON!',
            content_type="application/json",
            HTTP_AUTHORIZATION=f"apikey {self.user.username}:{self.api_key.plaintext_key}",
            HTTP_USER_AGENT="user agent string",
        )
        self.assertEqual(response.status_code, 400, response.content)

        log = RequestLog.objects.last()
        self.assertEqual(log.status, RequestLog.Status.VALIDATION_FAILED)
        attempt = log.processingattempt_set.last()
        self.assertEqual(attempt.raw_response, {"error": "Payload must be valid JSON"})

        reprocess_api_request(log)
        log.refresh_from_db()
        self.assertEqual(log.status, RequestLog.Status.VALIDATION_FAILED)
        self.assertEqual(log.processingattempt_set.count(), 2)
        attempt = log.processingattempt_set.last()
        self.assertEqual(attempt.is_retry, True)
        self.assertEqual(attempt.raw_response, {"error": "Payload must be valid JSON"})

    def test_archive_forms(self):
        properties_expression = {'prop': 'const'}
        self._call_api(properties_expression)

        log = RequestLog.objects.last()
        xform = XFormInstance.get_obj_by_id(log.processingattempt_set.last().xform_id)
        self.assertEqual(xform.is_archived, False)
        self.assertEqual(log.status, RequestLog.Status.SUCCESS)

        # Archive form(s) based on request log
        archive_api_request(log, self.user._id)
        log.refresh_from_db()
        xform.refresh_from_db()
        self.assertEqual(xform.is_archived, True)
        self.assertEqual(log.status, RequestLog.Status.REVERTED)

    def test_revert_log(self):
        properties_expression = {'prop': 'const'}
        self._call_api(properties_expression)

        log = RequestLog.objects.last()
        xform = XFormInstance.get_obj_by_id(log.processingattempt_set.last().xform_id)
        self.assertEqual(log.status, RequestLog.Status.SUCCESS)

        # Revert request log based on form
        revert_api_request_from_form(xform.form_id)
        log.refresh_from_db()
        self.assertEqual(log.status, RequestLog.Status.REVERTED)

    def test_create_duplicate_cases_with_external_id_create(self):
        case = create_case(self.domain_name, save=True, external_id="external_id")

        self.additional_post_data = {
            'external_id': case.external_id,
        }

        expression = UCRExpression.objects.create(
            name='create_sport',
            domain=self.domain_name,
            expression_type=UCR_NAMED_EXPRESSION,
            definition=self._expression_definition_with_external_id(should_create=True),
        )

        api = ConfigurableAPI.objects.create(
            domain=self.domain_name,
            filter_expression=None,
            transform_expression=expression,
            backend=ApiBackendOptions.json,
        )
        response = self._call_api_advanced(api, None)
        new_case = response.json()['cases'][0]
        self.assertEqual(new_case['external_id'], case.external_id)
        first_case_id = new_case['case_id']

        response = self._call_api_advanced(api, None)
        new_case = response.json()['cases'][0]
        self.assertEqual(new_case['external_id'], case.external_id)
        self.assertNotEqual(new_case['case_id'], first_case_id)

    def test_create_case_with_external_id_update(self):
        case = create_case(self.domain_name, save=True, external_id="external_id")

        self.additional_post_data = {
            'external_id': case.external_id,
        }

        expression = UCRExpression.objects.create(
            name='create_sport',
            domain=self.domain_name,
            expression_type=UCR_NAMED_EXPRESSION,
            definition=self._expression_definition_with_external_id(should_create=False),
        )

        api = ConfigurableAPI.objects.create(
            domain=self.domain_name,
            filter_expression=None,
            transform_expression=expression,
            backend=ApiBackendOptions.json,
        )
        response = self._call_api_advanced(api, None)
        new_case = response.json()['cases'][0]
        self.assertEqual(new_case['external_id'], case.external_id)

    def test_does_not_create_duplicate_cases_with_external_id_update(self):
        case = create_case(self.domain_name, save=True, external_id="external_id")

        self.additional_post_data = {
            'external_id': case.external_id,
        }

        expression = UCRExpression.objects.create(
            name='create_sport',
            domain=self.domain_name,
            expression_type=UCR_NAMED_EXPRESSION,
            definition=self._expression_definition_with_external_id(should_create=False),
        )

        api = ConfigurableAPI.objects.create(
            domain=self.domain_name,
            filter_expression=None,
            transform_expression=expression,
            backend=ApiBackendOptions.json,
        )
        response = self._call_api_advanced(api, None)
        new_case = response.json()['cases'][0]
        self.assertEqual(new_case['external_id'], case.external_id)
        first_case_id = new_case['case_id']

        response = self._call_api_advanced(api, None)
        new_case = response.json()['cases'][0]
        self.assertEqual(new_case['external_id'], case.external_id)
        self.assertEqual(new_case['case_id'], first_case_id)

    def _expression_definition_with_external_id(self, should_create):
        property_expressions = {
            "type": "dict",
            "name": {
                "type": "jsonpath",
                "datatype": "string",
                "jsonpath": "body.name"
            },
        }
        expression = self._get_ucr_case_expression(property_expressions)
        expression["properties"].update({
            "external_id": {
                "type": "jsonpath",
                "datatype": "string",
                "jsonpath": "body.external_id"
            }
        })
        expression["properties"]["create"] = should_create
        return expression
