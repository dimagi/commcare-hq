from mock import patch

from django.test.client import RequestFactory

import stripe

from corehq.apps.accounting.models import PaymentRecord, PaymentMethod, BillingAccount
from corehq.apps.accounting.payment_handlers import CreditStripePaymentHandler
from corehq.apps.accounting.tests import BaseAccountingTest
from corehq.apps.domain.models import Domain


class TestCreditStripePaymentHandler(BaseAccountingTest):

    def setUp(self):
        self.domain = Domain(name='test-domain')
        self.domain.save()
        self.payment_method = PaymentMethod()
        self.payment_method.save()
        self.account, _ = BillingAccount.get_or_create_account_by_domain(
            self.domain.name, created_by='webuser@test.com'
        )

    def tearDown(self):
        self.domain.delete()
        self.payment_method.delete()
        self.account.delete()
        super(TestCreditStripePaymentHandler, self).tearDown()

    @patch.object(stripe.Charge, 'create')
    def test_when_stripe_errors_no_payment_record_exists(self, mock_create):
        mock_create.side_effect = Exception

        self._call_process_request()

        self.assertEqual(PaymentRecord.objects.count(), 0)

    def _call_process_request(self):
        CreditStripePaymentHandler(
            self.payment_method, self.domain, self.account, post_data={}
        ).process_request(
            RequestFactory().post('', {'amount': 1})
        )
