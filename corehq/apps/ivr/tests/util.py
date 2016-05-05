from corehq.apps.ivr.models import Call
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.models import INCOMING
from corehq.apps.sms.util import register_sms_contact
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.utils.general import should_use_sql_backend
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
        self.domain = 'test-log-call-domain'
        self.delete_call_logs(self.domain)

    def tearDown(self):
        self.delete_call_logs(self.domain)
        VerifiedNumber.by_phone(self.phone_number).delete()

    def delete_case(self):
        if should_use_sql_backend(self.domain):
            CaseAccessorSQL.hard_delete_cases(self.domain, [self.case.case_id])
        else:
            self.case.delete()

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

    @run_with_all_backends
    def test_log_call(self):
        self.case_id = register_sms_contact(self.domain, 'participant', 'test',
            'system', self.phone_number)
        self.case = CaseAccessors(self.domain).get_case(self.case_id)

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
        self.assertEqual(call.couch_recipient, self.case.case_id)
        self.assertEqual(call.direction, INCOMING)

        self.delete_case()
