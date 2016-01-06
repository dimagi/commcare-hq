from casexml.apps.case.models import CommCareCase
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.models import CallLog, INCOMING
from corehq.apps.sms.util import register_sms_contact
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
        calls = CallLog.by_domain_asc(domain).all()
        if calls:
            CallLog.get_db().bulk_delete([
                call.to_json() for call in calls
            ])

    def setUp(self):
        self.domain = 'test-log-call-domain'
        self.delete_call_logs(self.domain)
        self.case_id = register_sms_contact(self.domain, 'participant', 'test',
            'system', self.phone_number)
        self.case = CommCareCase.get(self.case_id)

    def tearDown(self):
        self.delete_call_logs(self.domain)
        VerifiedNumber.by_phone(self.phone_number).delete()
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

    def test_log_call(self):
        if self.__class__ == LogCallTestCase:
            # The test runner picks up this base class too, but we only
            # want to run the test on subclasses.
            return

        self.assertEqual(CallLog.count_by_domain(self.domain), 0)
        response = self.simulate_inbound_call(self.phone_number)
        self.check_response(response)
        self.assertEqual(CallLog.count_by_domain(self.domain), 1)

        call = CallLog.by_domain_asc(self.domain).all()[0]
        self.assertEqual(call.couch_recipient_doc_type, 'CommCareCase')
        self.assertEqual(call.couch_recipient, self.case.get_id)
        self.assertEqual(call.direction, INCOMING)
