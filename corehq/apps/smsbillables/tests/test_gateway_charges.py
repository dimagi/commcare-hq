from decimal import Decimal

from django.test import TestCase
from unittest.mock import patch

from corehq.apps.sms.api import create_billable_for_sms
from corehq.apps.smsbillables.models import SmsBillable, SmsGatewayFee
from corehq.apps.smsbillables.tests.utils import get_fake_sms, short_text, long_text
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend


class TestGatewayChargeWithNoAPISupport(TestCase):
    """
    Test SmsBillable.gateway_charge for a backend that does not support an API
    """

    @classmethod
    def setUpClass(cls):
        super(TestGatewayChargeWithNoAPISupport, cls).setUpClass()
        cls.domain = 'sms_test_domain'

        cls.backend = SQLTestSMSBackend(
            name="TEST BACKEND",
            is_global=True,
            domain=cls.domain,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )
        cls.backend.save()

    @classmethod
    def tearDownClass(cls):
        cls.backend.delete()
        super(TestGatewayChargeWithNoAPISupport, cls).tearDownClass()

    def setUp(self):
        super(TestGatewayChargeWithNoAPISupport, self).setUp()
        self.billable = self.msg = None
        self.gateway_fees = []

    def tearDown(self):
        if self.billable is not None:
            self.billable.delete()
        if self.gateway_fees is not None:
            [gateway_fee.delete() for gateway_fee in self.gateway_fees]
        if self.msg is not None:
            self.msg.delete()
        super(TestGatewayChargeWithNoAPISupport, self).tearDown()

    def test_gateway_charge_general_criteria(self):
        """
        Create a gateway fee with no specific criteria and ensure gateway charge is expected
        """
        expected_gateway_charge = Decimal('0.01')
        self.msg = get_fake_sms(self.domain, self.backend.hq_api_id,
                                self.backend.couch_id, short_text)
        self.gateway_fees += [
            SmsGatewayFee.create_new(self.backend.hq_api_id, self.msg.direction, expected_gateway_charge),
        ]
        create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]

        actual_fee = self.billable.gateway_charge
        self.assertEqual(expected_gateway_charge, actual_fee)

    def test_gateway_charge_for_country_code(self):
        """
        Create a generic gateway fee and a specific gateway fee with country code
        """
        specific_gateway_fee_amount = Decimal('0.01')
        generic_gateway_fee_amount = Decimal('0.005')
        expected_gateway_charge = specific_gateway_fee_amount

        self.msg = get_fake_sms(self.domain, self.backend.hq_api_id,
                                self.backend.couch_id, short_text)
        self.gateway_fees += [
            SmsGatewayFee.create_new(self.backend.hq_api_id, self.msg.direction, generic_gateway_fee_amount),
            SmsGatewayFee.create_new(self.backend.hq_api_id, self.msg.direction, specific_gateway_fee_amount,
                                     country_code=1),
        ]
        create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]

        actual_gateway_charge = self.billable.gateway_charge
        self.assertEqual(expected_gateway_charge, actual_gateway_charge)


class TestGatewayChargeWithAPISupport(TestCase):
    """
    Test SmsBillable.gateway_charge for a backend that supports an API
    """

    @classmethod
    def setUpClass(cls):
        super(TestGatewayChargeWithAPISupport, cls).setUpClass()
        cls.domain = 'sms_test_api_domain'

        cls.backend = SQLTwilioBackend(
            name="TEST API BACKEND",
            is_global=True,
            domain=cls.domain,
            hq_api_id=SQLTwilioBackend.get_api_id()
        )
        cls.backend.save()

    @classmethod
    def tearDownClass(cls):
        cls.backend.delete()
        super(TestGatewayChargeWithAPISupport, cls).tearDownClass()

    def setUp(self):
        super(TestGatewayChargeWithAPISupport, self).setUp()
        self.billable = self.msg = None
        self.gateway_fees = []

    def tearDown(self):
        if self.billable is not None:
            self.billable.delete()
        if self.gateway_fees is not None:
            [gateway_fee.delete() for gateway_fee in self.gateway_fees]
        if self.msg is not None:
            self.msg.delete()
        super(TestGatewayChargeWithAPISupport, self).tearDown()

    def test_gateway_charge_with_api(self):
        """
        A backend that uses an API to fetch prices with a gateway_fee.amount = None should always return
        the price specified by the API
        """
        expected_gateway_charge = Decimal('0.01')
        self.msg = get_fake_sms(self.domain, self.backend.hq_api_id,
                                self.backend.couch_id, short_text)
        self.gateway_fees += [
            SmsGatewayFee.create_new(self.backend.hq_api_id, self.msg.direction, None),
        ]
        with patch('corehq.apps.smsbillables.models.SmsBillable.get_charge_details_through_api',
                   return_value=(expected_gateway_charge, 1)):
            create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]

        actual_gateway_charge = self.billable.gateway_charge
        self.assertEqual(expected_gateway_charge, actual_gateway_charge)

    def test_gateway_charge_with_api_and_matching_gateway_fee(self):
        """
        A backend with both a matching gateway_fee and an API should charge using the gateway_fee
        'Matching' means the message under test fits with the criteria set for the gateway_fee
        """
        api_fee = Decimal('0.01')
        gateway_fee_amount = Decimal('0.0075')
        # expect to charge the gateway_fee
        expected_gateway_charge = gateway_fee_amount

        self.msg = get_fake_sms(self.domain, self.backend.hq_api_id,
                                self.backend.couch_id, short_text)
        self.gateway_fees += [
            # the default number used in this test case has a country code of 1
            SmsGatewayFee.create_new(self.backend.hq_api_id, self.msg.direction, gateway_fee_amount,
                                     country_code=1),
        ]
        with patch('corehq.apps.smsbillables.models.SmsBillable.get_charge_details_through_api',
                   return_value=(api_fee, 1)):
            create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]

        actual_gateway_charge = self.billable.gateway_charge
        self.assertEqual(expected_gateway_charge, actual_gateway_charge)

    def test_gateway_charge_with_api_and_non_matching_gateway_fee(self):
        """
        A backend with non-matching gateway_fee and an API should charge using the API
        'Non-matching' means the message under test does not fit the gateway fee criteria
        """
        api_fee = Decimal('0.01')
        gateway_fee_amount = Decimal('0.0075')
        # expect to return the api price
        expected_gateway_charge = api_fee

        self.msg = get_fake_sms(self.domain, self.backend.hq_api_id,
                                self.backend.couch_id, short_text)

        self.gateway_fees += [
            # the default number here has a country code of 1, so make this code different
            SmsGatewayFee.create_new(self.backend.hq_api_id, self.msg.direction, gateway_fee_amount,
                                     country_code=10),
        ]
        with patch('corehq.apps.smsbillables.models.SmsBillable.get_charge_details_through_api',
                   return_value=(api_fee, 1)):
            create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]

        actual_gateway_charge = self.billable.gateway_charge
        self.assertEqual(expected_gateway_charge, actual_gateway_charge)

    def test_gateway_charge_with_api_and_non_matching_gateway_fee_multiple_messages(self):
        """
        A backend with non-matching gateway_fee and an API should charge using the API
        'Non-matching' means the message under test does not fit the gateway fee criteria
        ASSUMPTION: we assume that the API will return a value accounting for multiple messages if applicable
        This may be true for Twilio, but as we add other gateways that support an API we should check
        """
        api_fee = Decimal('0.01')
        gateway_fee_amount = Decimal('0.0075')
        # expect to return the api fee as is
        expected_gateway_charge = api_fee

        self.msg = get_fake_sms(self.domain, self.backend.hq_api_id,
                                self.backend.couch_id, long_text)

        self.gateway_fees += [
            # the default number here has a country code of 1, so make this code different
            SmsGatewayFee.create_new(self.backend.hq_api_id, self.msg.direction, gateway_fee_amount,
                                     country_code=10),
        ]
        with patch('corehq.apps.smsbillables.models.SmsBillable.get_charge_details_through_api',
                   return_value=(api_fee, 1)):
            create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]

        actual_gateway_charge = self.billable.gateway_charge
        self.assertEqual(expected_gateway_charge, actual_gateway_charge)

    def test_gateway_charge_with_api_and_matching_gateway_fee_multiple_messages(self):
        """
        A backend with non-matching gateway_fee and an API should charge using the API
        'Matching' means the message under test fits with the criteria set for the gateway_fee
        If using the gateway fee we need to do the calculation for the cost of multiple messages
        """
        api_fee = Decimal('0.01')
        gateway_fee_amount = Decimal('0.0075')
        # expect to return the gateway fee x 2 (long_text takes up 2 messages)
        expected_gateway_charge = gateway_fee_amount * 2

        self.msg = get_fake_sms(self.domain, self.backend.hq_api_id,
                                self.backend.couch_id, long_text)

        self.gateway_fees += [
            SmsGatewayFee.create_new(self.backend.hq_api_id, self.msg.direction, gateway_fee_amount),
        ]
        with patch('corehq.apps.smsbillables.models.SmsBillable.get_charge_details_through_api',
                   return_value=(api_fee, None)):
            create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]

        actual_gateway_charge = self.billable.gateway_charge
        self.assertEqual(expected_gateway_charge, actual_gateway_charge)
