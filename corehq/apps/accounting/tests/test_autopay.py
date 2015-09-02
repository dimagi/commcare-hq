import random
import mock

from stripe import Charge
from django.core import mail

from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from corehq.apps.accounting import generator, utils, tasks
from corehq.apps.accounting.generator import FakeStripeCard, FakeStripeCustomer
from corehq.apps.accounting.models import Invoice, StripePaymentMethod, PaymentRecord
from corehq.apps.accounting.payment_handlers import AutoPayInvoicePaymentHandler


class TestBillingAutoPay(BaseInvoiceTestCase):
    def setUp(self):
        super(TestBillingAutoPay, self).setUp()
        self.account.created_by_domain = self.domain
        self.account.save()

        self.currency = generator.init_default_currency()

        self.web_user = generator.arbitrary_web_user()
        self.dimagi_user = generator.arbitrary_web_user(is_dimagi=True)
        self.fake_card = FakeStripeCard()
        self.fake_stripe_customer = FakeStripeCustomer(cards=[self.fake_card])

        self.account.update_autopay_user(self.web_user.username)
        self.invoice_date = utils.months_from_date(self.subscription.date_start,
                                                   random.randint(2, self.subscription_length))
        self.payment_method = StripePaymentMethod(web_user=self.web_user.username,
                                                  customer_id=self.fake_stripe_customer.id)
        self.payment_method.set_autopay(self.fake_card, self.account)
        self.payment_method.save()

        self.account_2 = generator.billing_account(self.dimagi_user, self.web_user)
        self.domain_2 = generator.arbitrary_domain()

        self.subscription_2, self.subscription_length_2 = generator.generate_domain_subscription_from_date(
            generator.get_start_date(), self.account_2, self.domain_2.name,
            min_num_months=self.min_subscription_length,
        )

        tasks.generate_invoices(self.invoice_date)

    def test_get_autopayable_invoices(self):
        autopayable_invoice = Invoice.objects.filter(subscription=self.subscription)
        date_due = autopayable_invoice.first().date_due

        autopayable_invoices = Invoice.autopayable_invoices(date_due)

        self.assertItemsEqual(autopayable_invoices, autopayable_invoice)

    @mock.patch.object(StripePaymentMethod, 'customer')
    @mock.patch.object(Charge, 'create')
    def test_pay_autopayable_invoices(self, fake_charge, fake_customer):
        fake_customer.__get__ = mock.Mock(return_value=self.fake_stripe_customer)
        original_outbox_length = len(mail.outbox)

        autopayable_invoice = Invoice.objects.filter(subscription=self.subscription)
        date_due = autopayable_invoice.first().date_due

        AutoPayInvoicePaymentHandler().pay_autopayable_invoices(date_due)
        self.assertAlmostEqual(autopayable_invoice.first().get_total(), 0)
        self.assertEqual(len(PaymentRecord.objects.all()), 1)
        self.assertEqual(len(mail.outbox), original_outbox_length + 1)
