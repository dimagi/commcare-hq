from django.conf import settings
from django.test import TestCase
from corehq.apps.accounting.generator import init_default_currency

from corehq.apps.sms.models import SMSLog
from corehq.apps.sms.util import get_available_backends
from corehq.apps.smsbillables.models import *
from corehq.apps.smsbillables import generator


class TestGatewayFee(TestCase):
    def setUp(self):
        SmsGatewayFee.objects.all().delete()
        SmsGatewayFeeCriteria.objects.all().delete()

        self.currency_usd = init_default_currency()
        self.available_backends = generator.available_gateway_fee_backends()

        self.backend_ids = generator.arbitrary_backend_ids()
        self.message_logs = generator.arbitrary_messages_by_backend_and_direction(self.backend_ids)

        self.least_specific_fees = generator.arbitrary_fees_by_direction_and_backend()
        self.country_code_fees = generator.arbitrary_fees_by_country()
        self.instance_fees = generator.arbitrary_fees_by_backend_instance(self.backend_ids)
        self.most_specific_fees = generator.arbitrary_fees_by_all(self.backend_ids)
        self.country_code_and_prefixes = generator.arbitrary_country_code_and_prefixes()
        self.prefix_fees = generator.arbitrary_fees_by_prefix(self.backend_ids, self.country_code_and_prefixes)

        self.other_currency = generator.arbitrary_currency()

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
            messages = generator.arbitrary_messages_by_backend_and_direction(
                self.backend_ids,
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

    def tearDown(self):
        SmsBillable.objects.all().delete()
        SmsGatewayFee.objects.all().delete()
        SmsGatewayFeeCriteria.objects.all().delete()
        SmsUsageFee.objects.all().delete()
        SmsUsageFeeCriteria.objects.all().delete()

        self.currency_usd.delete()
        self.other_currency.delete()
        SMSLog.get_db().delete_docs(
            SMSLog.by_domain_asc(generator.TEST_DOMAIN).all()
        )

        backend_classes = get_available_backends(index_by_api_id=True)
        for api_id, backend_id in self.backend_ids.iteritems():
            backend_classes[api_id].get(backend_id).delete()
