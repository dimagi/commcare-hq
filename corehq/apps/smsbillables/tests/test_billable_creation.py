from decimal import Decimal

from django.test import TestCase

from corehq.apps.sms.api import create_billable_for_sms
from corehq.apps.sms.models import OUTGOING
from corehq.apps.smsbillables.models import SmsBillable, SmsGatewayFee
from corehq.apps.smsbillables.tests.utils import create_sms, short_text, long_text
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend


class TestBillableCreation(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestBillableCreation, cls).setUpClass()
        cls.domain = 'sms_test_domain'

        cls.backend = SQLTestSMSBackend(
            name="TEST",
            is_global=True,
            domain=cls.domain,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )
        cls.backend.save()

    @classmethod
    def tearDownClass(cls):
        cls.backend.delete()
        super(TestBillableCreation, cls).tearDownClass()

    def setUp(self):
        super(TestBillableCreation, self).setUp()
        self.billable = self.gateway_fee = self.msg = None

    def tearDown(self):
        if self.billable is not None:
            self.billable.delete()
        if self.gateway_fee is not None:
            self.gateway_fee.delete()
        if self.msg is not None:
            self.msg.delete()
        super(TestBillableCreation, self).tearDown()

    def test_creation(self):
        self.msg = create_sms(self.domain, self.backend, '+12223334444', OUTGOING, short_text)

        create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]
        self.assertEqual(self.billable.multipart_count, 1)

    def test_long_creation(self):
        self.msg = create_sms(self.domain, self.backend, '+12223334444', OUTGOING, long_text)

        create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]
        self.assertEqual(self.billable.multipart_count, 2)

    def test_gateway_fee_after_creation(self):
        expected_fee = Decimal('0.005')
        self.msg = create_sms(self.domain, self.backend, '+12223334444', OUTGOING, short_text)
        self.gateway_fee = SmsGatewayFee.create_new(self.backend.hq_api_id, self.msg.direction, expected_fee)

        create_billable_for_sms(self.msg, delay=False)

        sms_billables = SmsBillable.objects.filter(
            domain=self.domain,
            log_id=self.msg.couch_id
        )
        self.assertEqual(sms_billables.count(), 1)
        self.billable = sms_billables[0]
        actual_fee = self.billable.gateway_fee.amount
        self.assertEqual(expected_fee, actual_fee)
