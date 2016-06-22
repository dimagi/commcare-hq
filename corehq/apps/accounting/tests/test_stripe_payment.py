from mock import patch

from django.test import TransactionTestCase
from django.test.client import RequestFactory

import stripe

from corehq.apps.accounting.models import PaymentRecord, PaymentMethod, BillingAccount
from corehq.apps.accounting.payment_handlers import CreditStripePaymentHandler
from corehq.apps.domain.models import Domain


class TestCreditStripePaymentHandler(TransactionTestCase):

    def setUp(self):
        super(TestCreditStripePaymentHandler, self).setUp()
        self.domain = Domain(name='test-domain')
        self.domain.save()
        self.payment_method = PaymentMethod()
        self.payment_method.save()
        self.account, _ = BillingAccount.get_or_create_account_by_domain(
            self.domain.name, created_by='webuser@test.com'
        )

    def tearDown(self):
        self.domain.delete()
        PaymentRecord.objects.all().delete()
        self.payment_method.delete()
        self.account.delete()
        super(TestCreditStripePaymentHandler, self).tearDown()

    @patch.object(stripe.Charge, 'create')
    def test_working_process_request(self, mock_create):
        self._call_process_request()

        self.assertEqual(PaymentRecord.objects.count(), 1)
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

        try:
            self._call_process_request()
        except:
            pass

        self.assertEqual(PaymentRecord.objects.count(), 0)
        self.assertEqual(mock_create.call_count, 0)

    def _call_process_request(self):
        CreditStripePaymentHandler(
            self.payment_method, self.domain, self.account, post_data={}
        ).process_request(
            RequestFactory().post('', {'amount': 1})
        )
