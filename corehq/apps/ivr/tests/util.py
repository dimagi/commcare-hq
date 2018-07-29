from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.ivr.models import Call
from corehq.apps.sms.models import INCOMING
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.util.test_utils import create_test_case
from django.test import TestCase


class LogCallTestCase(TestCase):
    """
    A test case to be used to test when an ivr backend just logs an inbound
    call for someone calling in and does nothing else.
    """

    @property
    def phone_number(self):
        """
        Defined as a property so that tests for country-specific gateways
        can use a country-specifc number.
        """
        return '99900000000'

    def delete_call_logs(self, domain):
        Call.by_domain(domain).delete()

    def setUp(self):
        super(LogCallTestCase, self).setUp()
        self.domain = 'test-log-call-domain'
        self.delete_call_logs(self.domain)

    def tearDown(self):
        self.delete_call_logs(self.domain)
        super(LogCallTestCase, self).tearDown()

    def simulate_inbound_call(self, phone_number):
        """
        Should simulate a new inbound call coming into the view
        and return the response that hq gives to the gateway.
        """
        raise NotImplementedError("Please implement this method")

    def check_response(self, response):
        """
        Should assert that the response that hq gives to the gateway is correct.
        """
        raise NotImplementedError("Please implement this method")

    def create_case(self):
        case_properties = {
            'contact_phone_number': self.phone_number,
            'contact_phone_number_is_verified': '1',
        }
        return create_test_case(self.domain, 'contact', 'test',
            case_properties=case_properties, drop_signals=False)

    @run_with_all_backends
    def test_log_call(self):
        with self.create_case() as case:
            if self.__class__ == LogCallTestCase:
                # The test runner picks up this base class too, but we only
                # want to run the test on subclasses.
                return

            self.assertEqual(Call.by_domain(self.domain).count(), 0)
            response = self.simulate_inbound_call(self.phone_number)
            self.check_response(response)
            self.assertEqual(Call.by_domain(self.domain).count(), 1)

            call = Call.by_domain(self.domain)[0]
            self.assertEqual(call.couch_recipient_doc_type, 'CommCareCase')
            self.assertEqual(call.couch_recipient, case.case_id)
            self.assertEqual(call.direction, INCOMING)
