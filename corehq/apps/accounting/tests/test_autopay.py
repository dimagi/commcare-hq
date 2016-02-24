import datetime
import random
import mock

from stripe import Charge
from django.core import mail

from dimagi.utils.dates import add_months_to_date

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

        self.account.update_autopay_user(self.web_user.username, self.domain)
        self.invoice_date = utils.months_from_date(self.subscription.date_start,
                                                   random.randint(2, self.subscription_length))

        self.account_2 = generator.billing_account(self.dimagi_user, self.web_user)
        self.domain_2 = generator.arbitrary_domain()

        self.subscription_length_2 = self.min_subscription_length  # months
        subscription_start_date = datetime.date(2016, 2, 23)
        subscription_end_date = add_months_to_date(subscription_start_date, self.subscription_length_2)
        self.subscription_2 = generator.generate_domain_subscription(
            self.account,
            self.domain,
            date_start=subscription_start_date,
            date_end=subscription_end_date,
        )

        tasks.generate_invoices(self.invoice_date)

    @mock.patch.object(StripePaymentMethod, 'customer')
    def test_get_autopayable_invoices(self, fake_customer):
        fake_customer.__get__ = mock.Mock(return_value=self.fake_stripe_customer)
        self.payment_method = StripePaymentMethod(web_user=self.web_user.username,
                                                  customer_id=self.fake_stripe_customer.id)
        self.payment_method.set_autopay(self.fake_card, self.account, self.domain)
        self.payment_method.save()
        autopayable_invoice = Invoice.objects.filter(subscription=self.subscription)
        date_due = autopayable_invoice.first().date_due

        autopayable_invoices = Invoice.autopayable_invoices(date_due)

        self.assertItemsEqual(autopayable_invoices, autopayable_invoice)

    @mock.patch.object(StripePaymentMethod, 'customer')
    @mock.patch.object(Charge, 'create')
    def test_pay_autopayable_invoices(self, fake_charge, fake_customer):
        fake_customer.__get__ = mock.Mock(return_value=self.fake_stripe_customer)
        self.payment_method = StripePaymentMethod(web_user=self.web_user.username,
                                                  customer_id=self.fake_stripe_customer.id)
        self.payment_method.set_autopay(self.fake_card, self.account, self.domain)
        self.payment_method.save()
        original_outbox_length = len(mail.outbox)

        autopayable_invoice = Invoice.objects.filter(subscription=self.subscription)
        date_due = autopayable_invoice.first().date_due

        AutoPayInvoicePaymentHandler().pay_autopayable_invoices(date_due)

        autopayable_invoices = Invoice.autopayable_invoices(date_due)
        for invoice in autopayable_invoices:
            self.assertAlmostEqual(invoice.get_total(), 0)

        num_autopaid_invoices = autopayable_invoices.count()
        self.assertEqual(len(PaymentRecord.objects.all()), num_autopaid_invoices)
        self.assertEqual(len(mail.outbox), original_outbox_length + num_autopaid_invoices)
