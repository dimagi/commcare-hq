from random import choice, randint

from django.apps import apps
from django.test import TestCase

from mock import patch

from corehq import toggles
from corehq.apps.accounting.tests.generator import init_default_currency
from corehq.apps.sms.models import SMS, SQLMobileBackend
from corehq.apps.smsbillables.management.commands.bootstrap_usage_fees import (
    bootstrap_usage_fees,
)
from corehq.apps.smsbillables.models import (
    SmsBillable,
    SmsGatewayFee,
    SmsGatewayFeeCriteria,
    SmsUsageFee,
    SmsUsageFeeCriteria,
    add_twilio_gateway_fee,
)
from corehq.apps.smsbillables.tests import generator
from corehq.apps.smsbillables.tests.utils import FakeTwilioMessageFactory
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend


class TestGatewayFee(TestCase):

    def setUp(self):
        super(TestGatewayFee, self).setUp()
        self.currency_usd = init_default_currency()

        self.backend_ids = generator.arbitrary_backend_ids()
        self.message_logs = generator.arbitrary_messages_by_backend_and_direction(self.backend_ids)

        self.least_specific_fees = generator.arbitrary_fees_by_direction_and_backend()
        self.country_code_fees = generator.arbitrary_fees_by_country()
        self.instance_fees = generator.arbitrary_fees_by_backend_instance(self.backend_ids)
        self.most_specific_fees = generator.arbitrary_fees_by_all(self.backend_ids)
        self.country_code_and_prefixes = generator.arbitrary_country_code_and_prefixes(3, 3)
        self.prefix_fees = generator.arbitrary_fees_by_prefix(self.backend_ids, self.country_code_and_prefixes)

        self.other_currency = generator.arbitrary_currency()

        # Must remove existing data populated in migrations
        SmsGatewayFee.objects.all().delete()
        SmsGatewayFeeCriteria.objects.all().delete()

    def create_least_specific_gateway_fees(self):
        for direction, fees in self.least_specific_fees.items():
            for backend_api_id, amount in fees.items():
                SmsGatewayFee.create_new(backend_api_id, direction, amount)

    def create_other_currency_fees(self):
        for direction, fees in self.least_specific_fees.items():
            for backend_api_id, amount in fees.items():
                SmsGatewayFee.create_new(backend_api_id, direction, amount, currency=self.other_currency)

    def create_country_code_gateway_fees(self):
        for direction, backend in self.country_code_fees.items():
            for backend_api_id, country in backend.items():
                for country_code, amount in country.items():
                    SmsGatewayFee.create_new(backend_api_id, direction, amount, country_code=country_code)

    def create_instance_gateway_fees(self):
        for direction, backend in self.instance_fees.items():
            for backend_api_id, (backend_instance, amount) in backend.items():
                SmsGatewayFee.create_new(backend_api_id, direction, amount, backend_instance=backend_instance)

    def create_most_specific_gateway_fees(self):
        for direction, backend in self.most_specific_fees.items():
            for backend_api_id, country in backend.items():
                for country_code, (backend_instance, amount) in country.items():
                    SmsGatewayFee.create_new(backend_api_id, direction, amount,
                                             country_code=country_code, backend_instance=backend_instance)

    def create_prefix_gateway_fees(self):
        for direction, backend in self.prefix_fees.items():
            for backend_api_id, country in backend.items():
                for country_code, prfx in country.items():
                    for prefix, backend_instance_and_amount in prfx.items():
                        for backend_instance, amount in backend_instance_and_amount.items():
                            SmsGatewayFee.create_new(
                                backend_api_id,
                                direction,
                                amount,
                                country_code=country_code,
                                prefix=prefix,
                                backend_instance=backend_instance,
                            )

    def test_least_specific_fees(self):
        self.create_least_specific_gateway_fees()

        for msg_log in self.message_logs:
            billable = SmsBillable.create(msg_log)
            self.assertIsNotNone(billable)
            self.assertEqual(
                billable.gateway_charge,
                self.least_specific_fees[billable.direction][billable.gateway_fee.criteria.backend_api_id]
            )

    def test_multipart_gateway_charge(self):
        self.create_least_specific_gateway_fees()

        for msg_log in self.message_logs:
            multipart_count = randint(1, 10)
            billable = SmsBillable.create(msg_log, multipart_count=multipart_count)
            self.assertIsNotNone(billable)
            self.assertEqual(
                billable.gateway_charge,
                self.least_specific_fees
                [billable.direction]
                [billable.gateway_fee.criteria.backend_api_id] * multipart_count
            )

    def test_other_currency_fees(self):
        self.create_other_currency_fees()

        for msg_log in self.message_logs:
            billable = SmsBillable.create(msg_log)
            self.assertIsNotNone(billable)
            self.assertEqual(
                billable.gateway_charge,
                self.least_specific_fees[billable.direction][billable.gateway_fee.criteria.backend_api_id]
                / self.other_currency.rate_to_default
            )

    def test_country_code_fees(self):
        self.create_least_specific_gateway_fees()
        self.create_country_code_gateway_fees()

        phone_numbers = [generator.arbitrary_phone_number() for i in range(10)]
        for phone_number in phone_numbers:
            messages = generator.arbitrary_messages_by_backend_and_direction(self.backend_ids,
                                                                             phone_number=phone_number)
            for msg_log in messages:
                billable = SmsBillable.create(msg_log)
                self.assertIsNotNone(billable)
                self.assertEqual(
                    billable.gateway_charge,
                    self.country_code_fees[billable.direction]
                    [billable.gateway_fee.criteria.backend_api_id]
                    [int(phone_number[:-10])]
                )

    def test_instance_fees(self):
        self.create_least_specific_gateway_fees()
        self.create_country_code_gateway_fees()
        self.create_instance_gateway_fees()

        phone_numbers = [generator.arbitrary_phone_number() for i in range(10)]
        for phone_number in phone_numbers:
            messages = generator.arbitrary_messages_by_backend_and_direction(self.backend_ids,
                                                                             phone_number=phone_number)
            for msg_log in messages:
                billable = SmsBillable.create(msg_log)
                self.assertIsNotNone(billable)
                self.assertEqual(
                    billable.gateway_charge,
                    self.instance_fees[billable.direction]
                    [billable.gateway_fee.criteria.backend_api_id]
                    [1]
                )

    def test_specific_fees(self):
        self.create_least_specific_gateway_fees()
        self.create_country_code_gateway_fees()
        self.create_instance_gateway_fees()
        self.create_most_specific_gateway_fees()

        phone_numbers = [generator.arbitrary_phone_number() for i in range(10)]
        for phone_number in phone_numbers:
            messages = generator.arbitrary_messages_by_backend_and_direction(self.backend_ids,
                                                                             phone_number=phone_number)
            for msg_log in messages:
                billable = SmsBillable.create(msg_log)
                self.assertIsNotNone(billable)
                self.assertEqual(
                    billable.gateway_charge,
                    self.most_specific_fees[billable.direction]
                    [billable.gateway_fee.criteria.backend_api_id]
                    [int(phone_number[:-10])]
                    [1]
                )

    def test_prefix_fees(self):
        self.create_prefix_gateway_fees()

        for phone_number, prefix in generator.arbitrary_phone_numbers_and_prefixes(
            self.country_code_and_prefixes
        ):
            random_key = choice(list(self.backend_ids))
            messages = generator.arbitrary_messages_by_backend_and_direction(
                {random_key: self.backend_ids[random_key]},
                phone_number=phone_number,
            )

            for msg_log in messages:
                billable = SmsBillable.create(msg_log)
                self.assertIsNotNone(billable)
                try:
                    self.assertEqual(
                        billable.gateway_charge,
                        self.prefix_fees
                        [billable.direction]
                        [billable.gateway_fee.criteria.backend_api_id]
                        [phone_number[:-10]]
                        [prefix]
                        [msg_log.backend_id]
                    )
                except AssertionError:
                    raise Exception(
                        "Phone number: %s, " % phone_number
                        + "given prefix: %s, " % prefix
                        + "found prefix: %s" % billable.gateway_fee.criteria.prefix
                    )

    def test_no_matching_fee(self):
        self.create_least_specific_gateway_fees()
        self.create_country_code_gateway_fees()
        self.create_instance_gateway_fees()
        self.create_most_specific_gateway_fees()

        phone_numbers = [generator.arbitrary_phone_number() for i in range(10)]
        for phone_number in phone_numbers:
            messages = generator.arbitrary_messages_by_backend_and_direction(self.backend_ids,
                                                                             phone_number=phone_number,
                                                                             directions=['X', 'Y'])
            for msg_log in messages:
                billable = SmsBillable.create(msg_log)
                self.assertIsNotNone(billable)
                self.assertIsNone(billable.gateway_fee)

    def test_fee_for_non_global_backend(self):
        self.create_least_specific_gateway_fees()

        private_backend_ids = generator.arbitrary_non_global_backend_ids()
        messages = generator.arbitrary_messages_by_backend_and_direction(
            private_backend_ids)
        arbitrary_message = messages[randint(0, len(messages) - 1)]

        toggles.ENABLE_INCLUDE_SMS_GATEWAY_CHARGING.set(
            arbitrary_message.domain, True, toggles.NAMESPACE_DOMAIN)
        billable = SmsBillable.create(arbitrary_message)
        toggles.ENABLE_INCLUDE_SMS_GATEWAY_CHARGING.set(
            arbitrary_message.domain, False, toggles.NAMESPACE_DOMAIN)

        self.assertIsNotNone(billable)
        self.assertIsNotNone(billable.gateway_fee)
        self.assertEqual(billable.gateway_charge,
                         self.least_specific_fees[billable.direction]
                         [billable.gateway_fee.criteria.backend_api_id])


    @patch(
        'twilio.rest.api.v2010.account.message.MessageList.get',
        lambda self, message_id: FakeTwilioMessageFactory.get_message(message_id)
    )
    def test_twilio_global_backend(self):
        add_twilio_gateway_fee(apps)
        twilio_backend = SQLTwilioBackend.objects.create(
            name='TWILIO',
            is_global=True,
            hq_api_id=SQLTwilioBackend.get_api_id(),
            couch_id='global_backend',
        )
        twilio_backend.set_extra_fields(
            account_sid='sid',
            auth_token='token',
        )
        twilio_backend.save()

        messages = [
            message
            for phone_number in [generator.arbitrary_phone_number() for _ in range(10)]
            for message in generator.arbitrary_messages_by_backend_and_direction(
                {twilio_backend.hq_api_id: twilio_backend.couch_id}, phone_number=phone_number
            )
        ]
        for msg_log in messages:
            FakeTwilioMessageFactory.add_price_for_message(msg_log.backend_message_id, generator.arbitrary_fee())

        for msg_log in messages:
            multipart_count = randint(1, 10)  # Should be ignored
            billable = SmsBillable.create(msg_log, multipart_count=multipart_count)
            self.assertIsNotNone(billable)
            self.assertIsNotNone(billable.gateway_fee)
            self.assertEqual(
                billable.gateway_charge,
                FakeTwilioMessageFactory.get_price_for_message(msg_log.backend_message_id)
            )

    @patch('corehq.apps.smsbillables.models.log_smsbillables_error')
    @patch(
        'twilio.rest.api.v2010.account.message.MessageList.get',
        lambda self, message_id: FakeTwilioMessageFactory.get_message(message_id)
    )
    def test_twilio_domain_level_backend(self, mock_log_smsbillables_error):
        add_twilio_gateway_fee(apps)
        bootstrap_usage_fees(apps)
        twilio_backend = SQLTwilioBackend.objects.create(
            name='TWILIO',
            is_global=False,
            hq_api_id=SQLTwilioBackend.get_api_id(),
            couch_id='domain_backend',
        )
        twilio_backend.set_extra_fields(
            account_sid='sid',
            auth_token='token',
        )
        twilio_backend.save()

        messages = [
            message
            for phone_number in [generator.arbitrary_phone_number() for _ in range(10)]
            for message in generator.arbitrary_messages_by_backend_and_direction(
                {twilio_backend.hq_api_id: twilio_backend.couch_id}, phone_number=phone_number
            )
        ]
        for msg_log in messages:
            FakeTwilioMessageFactory.add_price_for_message(msg_log.backend_message_id, generator.arbitrary_fee())

        for msg_log in messages:
            multipart_count = randint(1, 10)  # Should be ignored
            billable = SmsBillable.create(msg_log, multipart_count=multipart_count)
            self.assertIsNotNone(billable)
            self.assertIsNone(billable.gateway_fee)
            self.assertEqual(billable.gateway_charge, 0)

        self.assertEqual(mock_log_smsbillables_error.call_count, 0)

    def tearDown(self):
        SmsBillable.objects.all().delete()
        SmsGatewayFee.objects.all().delete()
        SmsGatewayFeeCriteria.objects.all().delete()
        SmsUsageFee.objects.all().delete()
        SmsUsageFeeCriteria.objects.all().delete()

        self.currency_usd.delete()
        self.other_currency.delete()
        SMS.by_domain(generator.TEST_DOMAIN).delete()

        for api_id, backend_id in self.backend_ids.items():
            SQLMobileBackend.load(backend_id, is_couch_id=True).delete()

        FakeTwilioMessageFactory.backend_message_id_to_price = {}

        super(TestGatewayFee, self).tearDown()
