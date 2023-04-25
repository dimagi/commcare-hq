import json
from urllib.parse import urlencode

from django.urls import reverse

from corehq import privileges
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.motech.generic_inbound.models import ApiMiddleware
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

    def test_post_hl7(self):
        response_content = self._test_generic_api({
            'facility': {
                'type': 'jsonpath',
                'jsonpath': 'body.parsed.MSH.MSH_4.HD_1',
            }
        })
        # TODO: update response
        self.assertEqual(response_content, "MSH")

    def _test_generic_api(self, properties_expression):
        response = self._call_api(properties_expression, middleware=ApiMiddleware.hl7)
        response_content = response.content
        self.assertEqual(response.status_code, 200, response_content)
        return response_content
