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
        self._generate_autopayable_entities()
        self._generate_non_autopayable_entities()
        self._generate_invoices()

    def _generate_autopayable_entities(self):
        """
        Create account, domain and subscription linked to the autopay user that have autopay enabled
        """
        self.autopay_account = self.account
        self.autopay_account.created_by_domain = self.domain
        self.autopay_account.save()
        self.autopay_user = generator.arbitrary_web_user()
        self.fake_card = FakeStripeCard()
        self.fake_stripe_customer = FakeStripeCustomer(cards=[self.fake_card])
        self.autopay_account.update_autopay_user(self.autopay_user.username, self.domain)

    def _generate_non_autopayable_entities(self):
        """
        Create account, domain, and subscription linked to the autopay user, but that don't have autopay enabled
        """
        self.non_autopay_account = generator.billing_account(
            web_user_creator=generator.arbitrary_web_user(is_dimagi=True),
            web_user_contact=self.autopay_user
        )
        self.non_autopay_domain = generator.arbitrary_domain()
        # Non-autopay subscription has same parameters as the autopayable subscription
        self.non_autopay_subscription = generator.generate_domain_subscription(
            self.non_autopay_account,
            self.non_autopay_domain,
            date_start=self.subscription.date_start,
            date_end=add_months_to_date(self.subscription.date_start, self.subscription_length),
        )

    def _generate_invoices(self):
        """
        Create invoices for both autopayable and non-autopayable subscriptions
        """
        # invoice date is 2 months before the end of the subscription (this is arbitrary)
        invoice_date = utils.months_from_date(self.subscription.date_start, self.subscription_length - 2)
        tasks.generate_invoices(invoice_date)

    @mock.patch.object(StripePaymentMethod, 'customer')
    def test_get_autopayable_invoices(self, fake_customer):
        """
        Invoice.autopayable_invoices() should return invoices that can be automatically paid
        """
        self._create_autopay_method(fake_customer)
        autopayable_invoice = Invoice.objects.filter(subscription=self.subscription)
        date_due = autopayable_invoice.first().date_due

        autopayable_invoices = Invoice.autopayable_invoices(date_due)

        self.assertItemsEqual(autopayable_invoices, autopayable_invoice)

    def test_get_autopayable_invoices_returns_nothing(self):
        """
        Invoice.autopayable_invoices() should not return invoices if the customer does not have an autopay method
        """
        not_autopayable_invoice = Invoice.objects.filter(subscription=self.non_autopay_subscription)
        date_due = not_autopayable_invoice.first().date_due
        autopayable_invoices = Invoice.autopayable_invoices(date_due)
        self.assertItemsEqual(autopayable_invoices, [])


    @mock.patch.object(StripePaymentMethod, 'customer')
    @mock.patch.object(Charge, 'create')
    def test_pay_autopayable_invoices(self, fake_charge, fake_customer):
        self._create_autopay_method(fake_customer)

        original_outbox_length = len(mail.outbox)

        autopayable_invoice = Invoice.objects.filter(subscription=self.subscription)
        date_due = autopayable_invoice.first().date_due

        AutoPayInvoicePaymentHandler().pay_autopayable_invoices(date_due)
        self.assertAlmostEqual(autopayable_invoice.first().get_total(), 0)
        self.assertEqual(len(PaymentRecord.objects.all()), 1)
        self.assertEqual(len(mail.outbox), original_outbox_length + 1)

    def _create_autopay_method(self, fake_customer):
        fake_customer.__get__ = mock.Mock(return_value=self.fake_stripe_customer)
        self.payment_method = StripePaymentMethod(web_user=self.autopay_user.username,
                                                  customer_id=self.fake_stripe_customer.id)
        self.payment_method.set_autopay(self.fake_card, self.autopay_account, self.domain)
        self.payment_method.save()
