from __future__ import absolute_import
from __future__ import unicode_literals
from mock import patch

from django.test import TestCase
from django.test.client import RequestFactory

import stripe
from stripe.resource import StripeObject

from corehq.apps.accounting.models import PaymentRecord, PaymentMethod, BillingAccount
from corehq.apps.accounting.payment_handlers import CreditStripePaymentHandler
from corehq.apps.domain.models import Domain


class MockFailingStripeObject(object):

    @property
    def id(self):
        raise Exception


class TestCreditStripePaymentHandler(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestCreditStripePaymentHandler, cls).setUpClass()
        cls.domain = Domain(name='test-domain')
        cls.domain.save()
        cls.payment_method = PaymentMethod()
        cls.payment_method.save()
        cls.account, _ = BillingAccount.get_or_create_account_by_domain(
            cls.domain.name, created_by='webuser@test.com'
        )

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(TestCreditStripePaymentHandler, cls).tearDownClass()

    @patch.object(stripe.Charge, 'create')
    def test_working_process_request(self, mock_create):
        transaction_id = 'stripe_charge_id'
        mock_create.return_value = StripeObject(id=transaction_id)

        self._call_process_request()

        self.assertEqual(PaymentRecord.objects.count(), 1)
        self.assertEqual(PaymentRecord.objects.all()[0].transaction_id, transaction_id)
        self.assertEqual(mock_create.call_count, 1)

    @patch.object(stripe.Charge, 'create')
    def test_failure_after_checkpoint(self, mock_create):
        mock_create.return_value = MockFailingStripeObject()

        self._call_process_request()

        self.assertEqual(PaymentRecord.objects.count(), 1)
        self.assertEqual(PaymentRecord.objects.all()[0].transaction_id, 'temp')
        self.assertEqual(mock_create.call_count, 1)

    @patch.object(stripe.Charge, 'create')
    def test_when_stripe_errors_no_payment_record_exists(self, mock_create):
        mock_create.side_effect = Exception

        self._call_process_request()

        self.assertEqual(PaymentRecord.objects.count(), 0)

    @patch.object(stripe.Charge, 'create')
    @patch.object(PaymentRecord, 'create_record')
    def test_when_create_record_fails_stripe_is_not_charged(self, mock_create_record, mock_create):
        mock_create_record.side_effect = Exception

        self._call_process_request()

        self.assertEqual(PaymentRecord.objects.count(), 0)
        self.assertEqual(mock_create.call_count, 0)

    def _call_process_request(self):
        CreditStripePaymentHandler(
            self.payment_method, self.domain, self.account, post_data={}
        ).process_request(
            RequestFactory().post('', {'amount': 1})
        )
