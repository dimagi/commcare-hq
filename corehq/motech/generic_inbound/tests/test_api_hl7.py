from django.urls import reverse
from freezegun import freeze_time

from corehq import privileges
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.motech.generic_inbound.models import ApiBackendOptions, RequestLog, ProcessingAttempt
from corehq.motech.generic_inbound.tests.test_api import GenericInboundAPIViewBaseTest
from corehq.util.test_utils import flag_enabled, privilege_enabled


@privilege_enabled(privileges.API_ACCESS)
@flag_enabled('API_THROTTLE_WHITELIST')
class TestGenericInboundAPIViewHL7(GenericInboundAPIViewBaseTest):
    domain_name = 'ucr-api-test-hl7'

    def _get_post_data(self):
        message = "MSH|^~\\&|ADT1|GOOD HEALTH HOSPITAL|GHH LAB, INC.|GOOD HEALTH HOSPITAL|198808181126|SECURITY|" \
                  "ADT^A01^ADT_A01|MSG00001|P|2.8||"
        return (
            message,
            "x-application/hl7-v2+er7"
        )

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain_name)
        super().tearDownClass()

    @freeze_time('2023-05-02 13:01:51')
    def test_post_hl7(self):
        response_content = self._test_generic_api({
            'facility': {
                'type': 'jsonpath',
                'jsonpath': 'body.message.MSH.MSH_4.HD_1',
            }
        }).decode()
        log = RequestLog.objects.last()
        expected = 'MSH|^~\\&#||GOOD HEALTH HOSPITAL|ADT1|GOOD HEALTH HOSPITAL|20230502130151|||' \
                   f'{log.id.hex}|P|2.8\r' \
                   'MSA|AA|MSG00001|success'
        self.assertEqual(response_content, expected)
        self._check_logging(log, response_content)
        self._check_data(log, {"facility": "GOOD HEALTH HOSPITAL"})


    @freeze_time('2023-05-02 13:01:51')
    def test_post_not_supported_type(self):
        generic_api = self._make_api({}, backend=ApiBackendOptions.hl7)
        url = reverse('generic_inbound_api', args=[self.domain_name, generic_api.url_key])
        response = self.client.post(
            url, data={}, HTTP_AUTHORIZATION=f"apikey {self.user.username}:{self.api_key.key}"
        )
        self.assertEqual(response.status_code, 400)
        log = RequestLog.objects.last()
        expected = f"MSH|^~\\&#|||||20230502130151|||{log.id.hex}||2.8\r" \
                   "MSA|AE||Error parsing HL7: Invalid message"
        self.assertEqual(response.content.decode(), expected)

    @freeze_time('2023-05-02 13:01:51')
    def test_validation_errors(self):
        api = self._make_api(
            property_expressions={
                'facility': {
                    'type': 'jsonpath',
                    'jsonpath': 'body.message.MSH.MSH_4.HD_1',
                }
            },
            validation_expression={
                "type": "boolean_expression",
                "expression": {"type": "jsonpath", "jsonpath": "body.message_type.code"},
                "operator": "eq",
                "property_value": "OBS"
            },
            backend=ApiBackendOptions.hl7
        )
        response = self._call_api_advanced(api)
        self.assertEqual(response.status_code, 400, response.content)
        log = RequestLog.objects.last()
        expected = 'MSH|^~\\&#||GOOD HEALTH HOSPITAL|ADT1|GOOD HEALTH HOSPITAL|20230502130151|||' \
                   f'{log.id.hex}|P|2.8\r' \
                   'MSA|AE|MSG00001|validation error\r' \
                   'ERR||207|E||||Invalid request|HD'
        self.assertEqual(response.content.decode(), expected)

    def _check_logging(self, log, response_data):
        self.assertEqual(log.domain, self.domain_name)
        self.assertEqual(log.status, RequestLog.Status.SUCCESS)
        self.assertEqual(log.attempts, 1)
        self.assertEqual(log.response_status, 200)
        self.assertEqual(log.username, self.user.username)
        self.assertEqual(log.request_method, RequestLog.RequestMethod.POST)
        self.assertEqual(log.request_body, self._get_post_data()[0])
        self.assertIn('CONTENT_TYPE', log.request_headers)
        self.assertEqual(log.request_headers['HTTP_USER_AGENT'], 'user agent string')
        self.assertEqual(log.request_ip, '127.0.0.1')

        attempt = ProcessingAttempt.objects.last()
        self.assertEqual(attempt.is_retry, False)
        self.assertEqual(attempt.response_status, 200)
        self.assertTrue(bool(attempt.raw_response))
        self.assertEqual(len(attempt.case_ids), 1)
        self.assertEqual(attempt.external_response, response_data)

    def _check_data(self, log, expected_properties):
        attempt = ProcessingAttempt.objects.filter(log=log).last()
        case_ids = [c['case_id'] for c in attempt.raw_response.get('cases', [])]
        self.assertEqual(len(case_ids), 1)
        case = CommCareCase.objects.get_case(case_ids[0])
        actual_properties = {
            key: value
            for key, value in case.case_json.items()
            if key in expected_properties
        }
        self.assertDictEqual(actual_properties, expected_properties)



    def _test_generic_api(self, properties_expression):
        response = self._call_api(properties_expression, backend=ApiBackendOptions.hl7)
        response_content = response.content
        self.assertEqual(response.status_code, 200, response_content)
        return response_content
