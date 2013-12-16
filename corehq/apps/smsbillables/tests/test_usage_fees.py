from django.conf import settings
from django.test import TestCase

from corehq.apps.smsbillables.models import *
from corehq.apps.smsbillables import generator


class TestUsageFee(TestCase):
    def setUp(self):
        self.currency_usd, _ = Currency.objects.get_or_create(
            code=settings.DEFAULT_CURRENCY,
            name="Default Currency",
            symbol="$",
            rate_to_default=1.0
        )

        self.least_specific_fees = generator.arbitrary_fees_by_direction()

    def apply_direction_fee(self):
        for direction, amount in self.least_specific_fees.items():
            SmsUsageFee.create_new(direction, amount)

    def test_only_direction(self):
        self.apply_direction_fee()
        messages = generator.arbitrary_messages_by_backend_and_direction(generator.arbitrary_backend_ids())

        for message in messages:
            billable = SmsBillable.create(message)
            self.assertIsNotNone(billable)
            self.assertEqual(
                billable.usage_fee.amount,
                self.least_specific_fees[message.direction]
            )

    def test_domain_and_direction(self):
        raise NotImplementedError

    def test_log_no_usage_fee(self):
        raise NotImplementedError

    def tearDown(self):
        pass
