from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.api import create_billable_for_sms
from corehq.apps.sms.models import OUTGOING, INCOMING
from corehq.apps.smsbillables.models import SmsBillable, SmsGatewayFee
from corehq.apps.smsbillables.tests.utils import create_sms, long_text, short_text
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
from corehq.util.test_utils import flag_enabled


class TestGatewayCharge(TestCase):
    """
    Test SmsBillable.gateway_charge for a backend that does not support an API
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'sms_test_domain'

        cls.backend = SQLTestSMSBackend(
            name="TEST BACKEND",
            is_global=True,
            domain=cls.domain,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )
        cls.backend.save()

        cls.twilio_backend = SQLTwilioBackend(
            name="TEST API BACKEND",
            is_global=True,
            domain=cls.domain,
            hq_api_id=SQLTwilioBackend.get_api_id()
        )
        cls.twilio_backend.save()

        cls.non_global_backend = SQLTestSMSBackend(
            name="NON GLOBAL TEST BACKEND",
            is_global=False,
            domain=cls.domain,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )
        cls.non_global_backend.save()

    def test_gateway_fee_is_used_for_charge(self):
        msg = create_sms(self.domain, self.backend, '+12223334444', OUTGOING, short_text)
        SmsGatewayFee.create_new(self.backend.hq_api_id, msg.direction, Decimal('0.01'))
        create_billable_for_sms(msg, delay=False)
        billable = SmsBillable.objects.get(domain=self.domain, log_id=msg.couch_id)

        actual_charge = billable.gateway_charge

        self.assertEqual(Decimal('0.01'), actual_charge)

    def test_api_fee_is_used_for_charge(self):
        msg = create_sms(self.domain, self.twilio_backend, '+12223334444', OUTGOING, short_text)
        SmsGatewayFee.create_new(self.twilio_backend.hq_api_id, msg.direction, None)
        with patch('corehq.apps.smsbillables.models.SmsBillable.get_charge_details_through_api',
                   return_value=(Decimal('0.01'), 1)):
            create_billable_for_sms(msg, delay=False)
        billable = SmsBillable.objects.get(domain=self.domain, log_id=msg.couch_id)

        actual_charge = billable.gateway_charge

        self.assertEqual(Decimal('0.01'), actual_charge)

    def test_gateway_fee_is_used_if_specified_on_api_backend(self):
        msg = create_sms(self.domain, self.twilio_backend, '+12223334444', OUTGOING, short_text)
        SmsGatewayFee.create_new(self.twilio_backend.hq_api_id, msg.direction, Decimal('0.005'))
        with patch('corehq.apps.smsbillables.models.SmsBillable.get_charge_details_through_api',
                   return_value=(Decimal('0.01'), 1)):
            create_billable_for_sms(msg, delay=False)
        billable = SmsBillable.objects.get(domain=self.domain, log_id=msg.couch_id)

        actual_charge = billable.gateway_charge

        self.assertEqual(Decimal('0.005'), actual_charge)

    def test_gateway_fee_factors_in_multipart_count(self):
        msg = create_sms(self.domain, self.backend, '+12223334444', OUTGOING, long_text)
        SmsGatewayFee.create_new(self.backend.hq_api_id, msg.direction, Decimal('0.01'))
        create_billable_for_sms(msg, delay=False)
        billable = SmsBillable.objects.get(domain=self.domain, log_id=msg.couch_id)

        actual_charge = billable.gateway_charge

        # long_text == 2 messages
        self.assertEqual(Decimal('0.02'), actual_charge)

    def test_api_fee_ignores_multipart_count(self):
        """
        We assume that the API will return a value accounting for multiple messages if applicable
        This is true for Twilio, but as we add other gateways that support an API we need to verify this
        """
        msg = create_sms(self.domain, self.twilio_backend, '+12223334444', OUTGOING, long_text)
        SmsGatewayFee.create_new(self.twilio_backend.hq_api_id, msg.direction, None)
        with patch('corehq.apps.smsbillables.models.SmsBillable.get_charge_details_through_api',
                   return_value=(Decimal('0.03'), 2)):
            create_billable_for_sms(msg, delay=False)
        billable = SmsBillable.objects.get(domain=self.domain, log_id=msg.couch_id)

        actual_charge = billable.gateway_charge

        # long_text == 2 messages
        self.assertEqual(Decimal('0.03'), actual_charge)

    def test_gateway_conversion_rate_is_applied(self):
        currency = Currency.objects.create(name='test', code='TST', rate_to_default=Decimal('0.5'))
        msg = create_sms(self.domain, self.backend, '+12223334444', OUTGOING, short_text)
        SmsGatewayFee.create_new(self.backend.hq_api_id, msg.direction, Decimal('0.01'), currency=currency)
        create_billable_for_sms(msg, delay=False)
        billable = SmsBillable.objects.get(domain=self.domain, log_id=msg.couch_id)

        actual_charge = billable.gateway_charge

        # charge / currency_rate
        self.assertEqual(Decimal('0.02'), actual_charge)

    def test_phone_number_edge_case(self):
        """
        Discovered with tests generating random input. The number 200270303263 is parsed by the phonenumbers
        lib to have country_code = 20, and national_number = '270303263', omitting the '0' that follows the
        country_code. This because the area code in this case is '02', which omits the leading 0 when parsed.
        """
        msg = create_sms(self.domain, self.backend, '200270303263', OUTGOING, short_text)
        SmsGatewayFee.create_new(self.backend.hq_api_id, msg.direction, Decimal('0.1'))
        # NOTE: prefix is '2', not '02' due to how phonenumbers parses the number
        SmsGatewayFee.create_new(self.backend.hq_api_id, msg.direction, Decimal('0.005'), country_code=20,
                                 prefix='2', backend_instance=self.backend.couch_id)
        create_billable_for_sms(msg, delay=False)
        billable = SmsBillable.objects.get(domain=self.domain, log_id=msg.couch_id)

        actual_gateway_charge = billable.gateway_charge

        self.assertEqual(Decimal('0.005'), actual_gateway_charge)

    def test_non_global_backend_charge_is_zero(self):
        msg = create_sms(self.domain, self.non_global_backend, '+12223334444', OUTGOING, short_text)
        SmsGatewayFee.create_new(self.non_global_backend.hq_api_id, msg.direction, Decimal('0.01'))
        create_billable_for_sms(msg, delay=False)
        billable = SmsBillable.objects.get(domain=self.domain, log_id=msg.couch_id)

        actual_gateway_charge = billable.gateway_charge

        self.assertEqual(Decimal('0.0'), actual_gateway_charge)

    @flag_enabled('ENABLE_INCLUDE_SMS_GATEWAY_CHARGING')
    def test_non_global_backend_is_charged_if_flag_enabled(self):
        msg = create_sms(self.domain, self.non_global_backend, '+12223334444', OUTGOING, short_text)
        SmsGatewayFee.create_new(self.non_global_backend.hq_api_id, msg.direction, Decimal('0.01'))
        create_billable_for_sms(msg, delay=False)
        billable = SmsBillable.objects.get(domain=self.domain, log_id=msg.couch_id)

        actual_charge = billable.gateway_charge

        self.assertEqual(Decimal('0.01'), actual_charge)


class TestGetByCriteria(TestCase):
    """
    There can be multiple matching gateway fees for a message
    These tests detail various cases in which multiple gateway fees are setup with differing levels of specificity
    The more specific gateway fee is always used over the less specific one
    When the level of specificity is the same, the most recently created fee is used
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'sms_test_domain'
        cls.backend = SQLTestSMSBackend(
            name="TEST BACKEND",
            is_global=True,
            domain=cls.domain,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )
        cls.backend.save()

    def test_most_recently_created_gateway_fee_is_used(self):
        SmsGatewayFee.create_new(self.backend.hq_api_id, OUTGOING, Decimal('0.01'))
        SmsGatewayFee.create_new(self.backend.hq_api_id, OUTGOING, Decimal('0.05'))

        gateway_fee = SmsGatewayFee.get_by_criteria(self.backend.hq_api_id, OUTGOING)

        self.assertEqual(Decimal('0.05'), gateway_fee.amount)

    def test_only_matching_gateways_are_used(self):
        SmsGatewayFee.create_new(self.backend.hq_api_id, OUTGOING, Decimal('0.01'))
        SmsGatewayFee.create_new(self.backend.hq_api_id, INCOMING, Decimal('0.005'))

        gateway_fee = SmsGatewayFee.get_by_criteria(self.backend.hq_api_id, OUTGOING)

        self.assertEqual(Decimal('0.01'), gateway_fee.amount)

    def test_country_code_fee_used_over_generic_fee(self):
        SmsGatewayFee.create_new(self.backend.hq_api_id, OUTGOING, Decimal('0.01'))
        SmsGatewayFee.create_new(self.backend.hq_api_id, OUTGOING, Decimal('0.005'), country_code=1)

        gateway_fee = SmsGatewayFee.get_by_criteria(self.backend.hq_api_id, OUTGOING, country_code=1)

        self.assertEqual(Decimal('0.005'), gateway_fee.amount)

    def test_instance_fee_used_over_generic_fee(self):
        SmsGatewayFee.create_new(self.backend.hq_api_id, OUTGOING, Decimal('0.01'))
        SmsGatewayFee.create_new(
            self.backend.hq_api_id, OUTGOING, Decimal('0.005'), backend_instance=self.backend.couch_id
        )

        gateway_fee = SmsGatewayFee.get_by_criteria(
            self.backend.hq_api_id, OUTGOING, backend_instance=self.backend.couch_id
        )

        self.assertEqual(Decimal('0.005'), gateway_fee.amount)

    def test_instance_fee_used_over_country_code_fee(self):
        SmsGatewayFee.create_new(self.backend.hq_api_id, OUTGOING, Decimal('0.01'), country_code=1)
        SmsGatewayFee.create_new(
            self.backend.hq_api_id, OUTGOING, Decimal('0.005'), backend_instance=self.backend.couch_id
        )

        gateway_fee = SmsGatewayFee.get_by_criteria(
            self.backend.hq_api_id, OUTGOING, country_code=1, backend_instance=self.backend.couch_id
        )

        self.assertEqual(Decimal('0.005'), gateway_fee.amount)

    def test_country_code_and_instance_fee_used_over_instance_fee(self):
        SmsGatewayFee.create_new(
            self.backend.hq_api_id, OUTGOING, Decimal('0.005'), backend_instance=self.backend.couch_id
        )
        SmsGatewayFee.create_new(
            self.backend.hq_api_id, OUTGOING, Decimal('0.01'), country_code=1,
            backend_instance=self.backend.couch_id
        )

        gateway_fee = SmsGatewayFee.get_by_criteria(
            self.backend.hq_api_id, OUTGOING, country_code=1, backend_instance=self.backend.couch_id
        )

        self.assertEqual(Decimal('0.01'), gateway_fee.amount)

    def test_country_code_and_instance_fee_with_prefix_used_over_country_code_and_instance_fee(self):
        SmsGatewayFee.create_new(
            self.backend.hq_api_id, OUTGOING, Decimal('0.005'), country_code=1,
            backend_instance=self.backend.couch_id
        )
        SmsGatewayFee.create_new(
            self.backend.hq_api_id, OUTGOING, Decimal('0.01'), country_code=1, prefix='222',
            backend_instance=self.backend.couch_id
        )

        gateway_fee = SmsGatewayFee.get_by_criteria(
            self.backend.hq_api_id, OUTGOING, country_code=1, backend_instance=self.backend.couch_id,
            national_number='2223334444'
        )

        self.assertEqual(Decimal('0.01'), gateway_fee.amount)
