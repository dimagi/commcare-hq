from decimal import Decimal
from django.core import mail

from unittest import mock
from django_prbac.models import Role
import stripe
from stripe import StripeObject

from dimagi.utils.dates import add_months_to_date

from corehq.apps.accounting import utils
from corehq.apps.accounting.models import (
    CustomerInvoice,
    Invoice,
    PaymentRecord,
    SoftwarePlan,
    SoftwarePlanVersion,
    SoftwareProductRate,
    StripePaymentMethod,
)
from corehq.apps.accounting.payment_handlers import (
    AutoPayInvoicePaymentHandler,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.generator import (
    FakeStripeCardManager,
    FakeStripeCustomerManager,
)
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from corehq.apps.accounting.tests.utils import mocked_stripe_api


class BaseTestBillingAutoPay(BaseInvoiceTestCase):

    def setUp(self):
        super().setUp()
        self._generate_autopayable_entities()
        self._generate_non_autopayable_entities()

        # invoice date is 2 months before the end of the subscription (this is arbitrary)
        invoice_date = utils.get_first_day_x_months_later(self.subscription.date_start,
                                                          self.subscription_length - 2)
        self.create_invoices(invoice_date)

    def tearDown(self):
        self.non_autopay_domain.delete()
        super().tearDown()

    def _generate_autopayable_entities(self):
        """
        Create account, domain and subscription linked to the autopay user that have autopay enabled
        """
        self.autopay_account = self.account
        self.autopay_account.created_by_domain = self.domain
        self.autopay_account.save()
        web_user = generator.arbitrary_user(domain_name=self.domain.name, is_active=True, is_webuser=True)
        self.autopay_user_email = web_user.email
        self.fake_card = FakeStripeCardManager.create_card()
        self.fake_stripe_customer = FakeStripeCustomerManager.create_customer(cards=[self.fake_card])
        self.autopay_account.update_autopay_user(self.autopay_user_email, self.domain)

    def _generate_non_autopayable_entities(self):
        """
        Create account, domain, and subscription linked to the autopay user, but that don't have autopay enabled
        """
        self.non_autopay_account = generator.billing_account(
            web_user_creator=generator.create_arbitrary_web_user_name(is_dimagi=True),
            web_user_contact=self.autopay_user_email
        )
        self.non_autopay_domain = generator.arbitrary_domain()
        # Non-autopay subscription has same parameters as the autopayable subscription
        cheap_plan = SoftwarePlan.objects.create(name='cheap')
        cheap_product_rate = SoftwareProductRate.objects.create(monthly_fee=1.00, name=cheap_plan.name)
        cheap_plan_version = SoftwarePlanVersion.objects.create(
            plan=cheap_plan,
            product_rate=cheap_product_rate,
            role=Role.objects.first(),
        )
        self.non_autopay_subscription = generator.generate_domain_subscription(
            self.non_autopay_account,
            self.non_autopay_domain,
            plan_version=cheap_plan_version,
            date_start=self.subscription.date_start,
            date_end=add_months_to_date(self.subscription.date_start, self.subscription_length),
        )

    def _create_autopay_method(self, fake_customer):
        fake_customer.__get__ = mock.Mock(return_value=self.fake_stripe_customer)
        self.payment_method = StripePaymentMethod(web_user=self.autopay_user_email,
                                                  customer_id=self.fake_stripe_customer.id)
        self.payment_method.set_autopay(self.fake_card, self.autopay_account, self.domain)
        self.payment_method.save()

    def _run_autopay(self):
        raise NotImplementedError

    def _assert_no_side_effects(self):
        self.assertEqual(PaymentRecord.objects.count(), 0)
        self.assertEqual(len(mail.outbox), self.original_outbox_length)
        self.assertEqual(self.invoice.get_total(), self.original_invoice_total)


class TestBillingAutoPayInvoices(BaseTestBillingAutoPay):

    @mocked_stripe_api()
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
    @mock.patch.object(stripe.Charge, 'create')
    @mocked_stripe_api()
    def test_pay_autopayable_invoices(self, fake_charge, fake_customer):
        self._create_autopay_method(fake_customer)
        fake_charge.return_value = StripeObject(id='transaction_id')

        original_outbox_length = len(mail.outbox)

        autopayable_invoice = Invoice.objects.filter(subscription=self.subscription)
        date_due = autopayable_invoice.first().date_due

        AutoPayInvoicePaymentHandler().pay_autopayable_invoices(date_due)
        self.assertEqual(autopayable_invoice.first().get_total(), Decimal('0.00'))
        self.assertEqual(len(PaymentRecord.objects.all()), 1)
        self.assertEqual(len(mail.outbox), original_outbox_length + 1)

    @mock.patch.object(StripePaymentMethod, 'customer')
    @mock.patch.object(stripe.Charge, 'create')
    @mocked_stripe_api()
    def test_double_charge_is_prevented_because_paid_invoice_is_never_included(self, fake_charge, fake_customer):
        self._create_autopay_method(fake_customer)
        self.original_outbox_length = len(mail.outbox)
        fake_charge.return_value = StripeObject(id='transaction_id')

        invoice = Invoice.objects.get(subscription=self.subscription)
        invoice.balance = Decimal('1000.0000')
        invoice.save()

        autopay_invoices = Invoice.autopayable_invoices(invoice.date_due)
        self.assertEqual(len(autopay_invoices), 1)
        self.assertEqual(autopay_invoices[0].id, invoice.id)

        fake_charge.return_value = StripeObject(id='transaction_id')
        self._run_autopay()
        self.assertEqual(len(PaymentRecord.objects.all()), 1)

        autopay_invoices = Invoice.autopayable_invoices(invoice.date_due)
        self.assertEqual(len(autopay_invoices), 0)

        self._run_autopay()
        self.assertEqual(len(PaymentRecord.objects.all()), 1)

    @mock.patch.object(StripePaymentMethod, 'customer')
    @mock.patch.object(stripe.Charge, 'create')
    @mocked_stripe_api()
    def test_when_stripe_fails_no_side_effects_occur(self, fake_create, fake_customer):
        fake_create.side_effect = Exception
        self._create_autopay_method(fake_customer)

        self.invoice = Invoice.objects.get(subscription=self.subscription)
        self.original_invoice_total = self.invoice.get_total()
        self.original_outbox_length = len(mail.outbox)

        self._run_autopay()
        self._assert_no_side_effects()

    def _run_autopay(self):
        autopayable_invoice = Invoice.objects.filter(subscription=self.subscription)
        date_due = autopayable_invoice.first().date_due
        AutoPayInvoicePaymentHandler().pay_autopayable_invoices(date_due)


class TestBillingAutoPayCustomerInvoices(BaseTestBillingAutoPay):
    def _generate_autopayable_entities(self):
        super()._generate_autopayable_entities()
        self.autopay_account.is_customer_billing_account = True
        self.autopay_account.save()

    def _generate_non_autopayable_entities(self):
        super()._generate_non_autopayable_entities()
        self.non_autopay_account.is_customer_billing_account = True
        self.non_autopay_account.save()

    @mocked_stripe_api()
    @mock.patch.object(StripePaymentMethod, 'customer')
    def test_get_autopayable_invoices(self, fake_customer):
        """
        CustomerInvoice.autopayable_invoices() should return invoices that can be automatically paid
        """
        self._create_autopay_method(fake_customer)
        autopayable_invoice = CustomerInvoice.objects.filter(account=self.autopay_account)
        date_due = autopayable_invoice.first().date_due

        autopayable_invoices = CustomerInvoice.autopayable_invoices(date_due)

        self.assertItemsEqual(autopayable_invoices, autopayable_invoice)

    def test_get_autopayable_invoices_returns_nothing(self):
        """
        CustomerInvoice.autopayable_invoices() should not return invoices if
        the customer does not have an autopay method
        """
        not_autopayable_invoice = CustomerInvoice.objects.filter(account=self.non_autopay_account)
        date_due = not_autopayable_invoice.first().date_due
        autopayable_invoices = CustomerInvoice.autopayable_invoices(date_due)
        self.assertItemsEqual(autopayable_invoices, [])

    @mock.patch.object(StripePaymentMethod, 'customer')
    @mock.patch.object(stripe.Charge, 'create')
    @mocked_stripe_api()
    def test_pay_autopayable_customer_invoices(self, fake_charge, fake_customer):
        self._create_autopay_method(fake_customer)
        fake_charge.return_value = StripeObject(id='transaction_id')

        original_outbox_length = len(mail.outbox)

        autopayable_invoice = CustomerInvoice.objects.filter(account=self.autopay_account)
        date_due = autopayable_invoice.first().date_due

        AutoPayInvoicePaymentHandler().pay_autopayable_customer_invoices(date_due)
        self.assertEqual(autopayable_invoice.first().get_total(), Decimal('0.00'))
        self.assertEqual(len(PaymentRecord.objects.all()), 1)
        self.assertEqual(len(mail.outbox), original_outbox_length + 1)

    @mock.patch.object(StripePaymentMethod, 'customer')
    @mock.patch.object(stripe.Charge, 'create')
    @mocked_stripe_api()
    def test_double_charge_is_prevented_because_paid_invoice_is_never_included(self, fake_charge, fake_customer):
        self._create_autopay_method(fake_customer)
        self.original_outbox_length = len(mail.outbox)
        fake_charge.return_value = StripeObject(id='transaction_id')

        invoice = CustomerInvoice.objects.get(account=self.autopay_account)
        invoice.balance = Decimal('1000.0000')
        invoice.save()

        autopay_invoices = CustomerInvoice.autopayable_invoices(invoice.date_due)
        self.assertEqual(len(autopay_invoices), 1)
        self.assertEqual(autopay_invoices[0].id, invoice.id)

        fake_charge.return_value = StripeObject(id='transaction_id')
        self._run_autopay()
        self.assertEqual(len(PaymentRecord.objects.all()), 1)

        autopay_invoices = CustomerInvoice.autopayable_invoices(invoice.date_due)
        self.assertEqual(len(autopay_invoices), 0)

        self._run_autopay()
        self.assertEqual(len(PaymentRecord.objects.all()), 1)

    @mock.patch.object(StripePaymentMethod, 'customer')
    @mock.patch.object(stripe.Charge, 'create')
    @mocked_stripe_api()
    def test_when_stripe_fails_no_side_effects_occur(self, fake_create, fake_customer):
        fake_create.side_effect = Exception
        self._create_autopay_method(fake_customer)

        self.invoice = CustomerInvoice.objects.get(account=self.autopay_account)
        self.original_invoice_total = self.invoice.get_total()
        self.original_outbox_length = len(mail.outbox)

        self._run_autopay()
        self._assert_no_side_effects()

    def _run_autopay(self):
        autopayable_invoice = CustomerInvoice.objects.filter(account=self.autopay_account)
        date_due = autopayable_invoice.first().date_due
        AutoPayInvoicePaymentHandler().pay_autopayable_customer_invoices(date_due)
