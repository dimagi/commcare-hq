from django.test import TestCase

# from corehq.apps.accounting import generator as gen_accounting
from corehq.apps.sms.models import SMSLog
from corehq.apps.sms.util import get_available_backends
from corehq.apps.smsbillables.models import *
from corehq.apps.smsbillables import generator


class TestGatewayFee(TestCase):

    def setUp(self):
        # self.currency_usd = gen_accounting.currency_usd()
        self.available_backends = get_available_backends().values()

        self.least_specific_fees = generator.arbitrary_fees_by_direction_and_backend()
        self.instance_fees = generator.arbitrary_fees_by_direction_and_backend()
        self.country_code_fees = generator.arbitrary_fees_by_direction_and_backend()
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
        # todo
        pass

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
        # self.currency_usd.delete()
        for log in SMSLog.by_domain_asc(generator.TEST_DOMAIN):
            log.delete()
