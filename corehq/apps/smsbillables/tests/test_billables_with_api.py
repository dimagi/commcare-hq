from decimal import Decimal

from django.test import TestCase
from mock import patch

from corehq.apps.sms.api import create_billable_for_sms
from corehq.apps.smsbillables.models import SmsBillable
from corehq.apps.smsbillables.tests.utils import create_gateway_fee, get_fake_sms, short_text, long_text
from corehq.messaging.smsbackends.test.models import SQLTestSMSWithAPIBackend


class TestSMSBillablesWithAPI(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestSMSBillablesWithAPI, cls).setUpClass()
        cls.domain = 'sms_test_api_domain'

        cls.backend = SQLTestSMSWithAPIBackend(
            name="TEST API",
            is_global=True,
            domain=cls.domain,
            hq_api_id=SQLTestSMSWithAPIBackend.get_api_id()
        )
        cls.backend.save()

    @classmethod
    def tearDownClass(cls):
        cls.backend.delete()
        super(TestSMSBillablesWithAPI, cls).tearDownClass()

    def setUp(self):
        super(TestSMSBillablesWithAPI, self).setUp()
        self.billable = self.gateway_fee = self.msg = None

    def tearDown(self):
        if self.billable is not None:
            self.billable.delete()
        if self.gateway_fee is not None:
            self.gateway_fee.delete()
        if self.msg is not None:
            self.msg.delete()
        super(TestSMSBillablesWithAPI, self).tearDown()

    def test_direct_gateway_fee(self):
        """
        A backend that uses an API to fetch prices with no specified gateway_fee amount should always return
        the price specified by the API
        """
        expected_direct_fee = Decimal('0.01')
        self.msg = get_fake_sms(self.domain, self.backend.hq_api_id,
                                self.backend.couch_id, short_text)
        self.gateway_fee = create_gateway_fee(self.backend.hq_api_id, self.msg, None)

        with patch('corehq.apps.smsbillables.models.SmsBillable.get_charge_details_through_api',
                   return_value=(expected_direct_fee, 1)):
            create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]

        actual_fee = self.billable.gateway_charge
        self.assertEqual(expected_direct_fee, actual_fee)

    def test_gateway_charge_with_api_and_matching_gateway_fee(self):
        """
        A backend with both a matching gateway_fee and an API should use the gateway_fee
        'Matching' means the message under test fits with the criteria set for the gateway_fee
        """
        api_fee = Decimal('0.01')
        gateway_fee = Decimal('0.0075')
        # expect to charge the gateway_fee
        expected_fee = gateway_fee

        self.msg = get_fake_sms(self.domain, self.backend.hq_api_id,
                                self.backend.couch_id, short_text)
        # the default number used in this test case has a country code of 1
        self.gateway_fee = create_gateway_fee(self.backend.hq_api_id, self.msg, gateway_fee, country_code=1)
        with patch('corehq.apps.smsbillables.models.SmsBillable.get_charge_details_through_api',
                   return_value=(api_fee, 1)):
            create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]

        actual_fee = self.billable.gateway_charge
        self.assertEqual(expected_fee, actual_fee)

    def test_gateway_charge_with_api_and_non_matching_gateway_fee(self):
        """
        A backend with non-matching gateway_fee and an API should use the API
        'Non-matching' means the message under test does not fit the gateway fee criteria
        """
        api_fee = Decimal('0.01')
        gateway_fee = Decimal('0.0075')
        # expect to return the api price
        expected_fee = api_fee

        self.msg = get_fake_sms(self.domain, self.backend.hq_api_id,
                                self.backend.couch_id, short_text)

        # the default number here has a country code of 1, so make this code different
        self.gateway_fee = create_gateway_fee(self.backend.hq_api_id, self.msg, gateway_fee, country_code=10)

        with patch('corehq.apps.smsbillables.models.SmsBillable.get_charge_details_through_api',
                   return_value=(api_fee, 1)):
            create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]

        actual_fee = self.billable.gateway_charge
        self.assertEqual(expected_fee, actual_fee)

    def test_gateway_charge_with_api_and_non_matching_gateway_fee_multiple_messages(self):
        """
        A backend with non-matching gateway_fee and an API should use the API
        'Non-matching' means the message under test does not fit the gateway fee criteria
        ASSUMPTION: we assume that the API will return a value accounting for multiple messages if applicable
        This may be true for Twilio, but as we add other gateways that support an API we should be careful
        """
        api_fee = Decimal('0.01')
        gateway_fee = Decimal('0.0075')
        # expect to return the api fee as is
        expected_fee = api_fee

        self.msg = get_fake_sms(self.domain, self.backend.hq_api_id,
                                self.backend.couch_id, long_text)

        # the default number here has a country code of 1, so make this code different
        self.gateway_fee = create_gateway_fee(self.backend.hq_api_id, self.msg, gateway_fee, country_code=10)

        with patch('corehq.apps.smsbillables.models.SmsBillable.get_charge_details_through_api',
                   return_value=(api_fee, 1)):
            create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]

        actual_fee = self.billable.gateway_charge
        self.assertEqual(expected_fee, actual_fee)

    def test_gateway_charge_with_api_and_matching_gateway_fee_multiple_messages(self):
        """
        A backend with non-matching gateway_fee and an API should use the API
        'Matching' means the message under test fits with the criteria set for the gateway_fee
        If using the gateway fee we need to do the calculation for the cost of multiple messages
        """
        api_fee = Decimal('0.01')
        gateway_fee = Decimal('0.0075')
        # expect to return the gateway fee x 2 (long_text takes up 2 messages)
        expected_fee = gateway_fee * 2

        self.msg = get_fake_sms(self.domain, self.backend.hq_api_id,
                                self.backend.couch_id, long_text)

        # the default number here has a country code of 1, so make this code different
        self.gateway_fee = create_gateway_fee(self.backend.hq_api_id, self.msg, gateway_fee)

        with patch('corehq.apps.smsbillables.models.SmsBillable.get_charge_details_through_api',
                   return_value=(api_fee, None)):
            create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]

        actual_fee = self.billable.gateway_charge
        self.assertEqual(expected_fee, actual_fee)
