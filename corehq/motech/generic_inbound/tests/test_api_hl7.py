from freezegun import freeze_time

from corehq import privileges
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.motech.generic_inbound.models import ApiMiddleware, RequestLog
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
            middleware=ApiMiddleware.hl7
        )
        response = self._call_api_advanced(api)
        self.assertEqual(response.status_code, 400, response.content)
        log = RequestLog.objects.last()
        expected = 'MSH|^~\\&#||GOOD HEALTH HOSPITAL|ADT1|GOOD HEALTH HOSPITAL|20230502130151|||' \
                   f'{log.id.hex}|P|2.8\r' \
                   'MSA|AE|MSG00001|validation error\r' \
                   'ERR||207|E||||Invalid request|HD'
        self.assertEqual(response.content.decode(), expected)

    def _test_generic_api(self, properties_expression):
        response = self._call_api(properties_expression, middleware=ApiMiddleware.hl7)
        response_content = response.content
        self.assertEqual(response.status_code, 200, response_content)
        return response_content
