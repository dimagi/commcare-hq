from random import randint

from django.conf import settings
from django.test import TestCase
from corehq.apps.accounting.generator import init_default_currency

from corehq.apps.smsbillables.models import *
from corehq.apps.smsbillables import generator
from corehq.apps.sms.models import SQLMobileBackend


class TestUsageFee(TestCase):
    def setUp(self):
        SmsUsageFee.objects.all().delete()
        SmsUsageFeeCriteria.objects.all().delete()

        self.currency_usd = init_default_currency()

        self.least_specific_fees = generator.arbitrary_fees_by_direction()
        self.most_specific_fees = generator.arbitrary_fees_by_direction_and_domain()
        self.backend_ids = generator.arbitrary_backend_ids()

    def apply_direction_fee(self):
        for direction, amount in self.least_specific_fees.items():
            SmsUsageFee.create_new(direction, amount)

    def apply_direction_and_domain_fee(self):
        for direction, domain_fee in self.most_specific_fees.items():
            for domain, amount in domain_fee.items():
                SmsUsageFee.create_new(direction, amount, domain=domain)

    def test_only_direction(self):
        self.apply_direction_fee()
        messages = generator.arbitrary_messages_by_backend_and_direction(self.backend_ids)

        for message in messages:
            billable = SmsBillable.create(message)
            self.assertIsNotNone(billable)
            self.assertEqual(
                billable.usage_charge,
                self.least_specific_fees[message.direction]
            )

    def test_domain_and_direction(self):
        self.apply_direction_fee()
        self.apply_direction_and_domain_fee()

        for direction, domain_fee in self.most_specific_fees.items():
            for domain in domain_fee:
                messages = generator.arbitrary_messages_by_backend_and_direction(
                    self.backend_ids,
                    domain=domain,
                )
                for message in messages:
                    billable = SmsBillable.create(message)
                    self.assertIsNotNone(billable)
                    self.assertEqual(
                        billable.usage_charge,
                        self.most_specific_fees[message.direction][domain]
                    )

    def test_multipart_usage_charge(self):
        self.apply_direction_fee()
        self.apply_direction_and_domain_fee()

        for direction, domain_fee in self.most_specific_fees.items():
            for domain in domain_fee:
                messages = generator.arbitrary_messages_by_backend_and_direction(
                    self.backend_ids,
                    domain=domain,
                )
                for message in messages:
                    multipart_count = randint(1, 10)
                    billable = SmsBillable.create(message, multipart_count=multipart_count)
                    self.assertIsNotNone(billable)
                    self.assertEqual(
                        billable.usage_charge,
                        self.most_specific_fees[message.direction][domain] * multipart_count
                    )

    def test_log_no_usage_fee(self):
        self.apply_direction_fee()
        self.apply_direction_and_domain_fee()

        for direction, domain_fee in self.most_specific_fees.items():
            for domain in domain_fee:
                messages = generator.arbitrary_messages_by_backend_and_direction(
                    self.backend_ids,
                    domain=domain,
                    directions=['X', 'Y'],
                )
                for message in messages:
                    billable = SmsBillable.create(message)
                    self.assertIsNotNone(billable)
                    self.assertIsNone(billable.usage_fee)

    def tearDown(self):
        SmsBillable.objects.all().delete()
        SmsUsageFee.objects.all().delete()
        SmsUsageFeeCriteria.objects.all().delete()
        SmsGatewayFee.objects.all().delete()
        self.currency_usd.delete()
        for api_id, backend_id in self.backend_ids.iteritems():
            SQLMobileBackend.load(backend_id, is_couch_id=True).delete()
