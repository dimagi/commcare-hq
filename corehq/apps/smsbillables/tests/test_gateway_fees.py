from django.conf import settings
from django.test import TestCase

from corehq.apps.sms.models import SMSLog
from corehq.apps.sms.util import get_available_backends
from corehq.apps.smsbillables.models import *
from corehq.apps.smsbillables import generator


class TestGatewayFee(TestCase):
    def setUp(self):
        self.currency_usd, _ = Currency.objects.get_or_create(
            code=settings.DEFAULT_CURRENCY,
            name="Default Currency",
            symbol="$",
            rate_to_default=1.0
        )
        self.available_backends = get_available_backends().values()

        self.least_specific_fees = generator.arbitrary_fees_by_direction_and_backend()
        self.instance_fees = generator.arbitrary_fees_by_direction_and_backend()
        self.country_code_fees = generator.arbitrary_fees_by_country()
        self.most_specific_fees = generator.arbitrary_fees_by_direction_and_backend()

        self.backend_ids = generator.arbitrary_backend_ids()
        self.message_logs = generator.arbitrary_messages_by_backend_and_direction(self.backend_ids)

    def test_least_specific_fees(self):
        for direction, fees in self.least_specific_fees.items():
            for backend_api_id, amount in fees.items():
                SmsGatewayFee.create_new(backend_api_id, direction, amount)

        for msg_log in self.message_logs:
            billable = SmsBillable.create(msg_log)
            self.assertIsNotNone(billable)
            self.assertEqual(
                billable.gateway_fee.amount,
                self.least_specific_fees[billable.direction][billable.gateway_fee.criteria.backend_api_id]
            )

    def test_country_code_fees(self):
        for direction, fees in self.least_specific_fees.items():
            for backend_api_id, amount in fees.items():
                SmsGatewayFee.create_new(backend_api_id, direction, amount)
        for direction, backend in self.country_code_fees.items():
            for backend_api_id, country in backend.items():
                for country_code, amount in country.items():
                    SmsGatewayFee.create_new(backend_api_id, direction, amount, country_code=country_code)

        phone_numbers = [generator.arbitrary_phone_number() for i in range(10)]
        for phone_number in phone_numbers:
            messages = generator.arbitrary_messages_by_backend_and_direction(self.backend_ids,
                                                                             phone_number=phone_number)
            for msg_log in messages:
                billable = SmsBillable.create(msg_log)
                self.assertIsNotNone(billable)
                self.assertEqual(
                    billable.gateway_fee.amount,
                    self.country_code_fees[billable.direction]
                    [billable.gateway_fee.criteria.backend_api_id]
                    [int(phone_number[:-10])]
                )


    def test_instance_fees(self):
        # todo
        pass

    def test_specific_fees(self):
        # todo
        pass

    def test_no_matching_fee(self):
        # todo
        pass

    def tearDown(self):
        SmsBillable.objects.all().delete()
        SmsGatewayFee.objects.all().delete()
        SmsGatewayFeeCriteria.objects.all().delete()
        SmsUsageFee.objects.all().delete()
        SmsUsageFeeCriteria.objects.all().delete()
        self.currency_usd.delete()
        for log in SMSLog.by_domain_asc(generator.TEST_DOMAIN):
            log.delete()
