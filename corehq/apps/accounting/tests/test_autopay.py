from django.core import mail

import mock
from django_prbac.models import Role
from stripe import Charge
from stripe.stripe_object import StripeObject

from dimagi.utils.dates import add_months_to_date

from corehq.apps.accounting import tasks, utils
from corehq.apps.accounting.models import (
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
    FakeStripeCard,
    FakeStripeCustomer,
)
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase


class TestBillingAutoPay(BaseInvoiceTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestBillingAutoPay, cls).setUpClass()
        cls._generate_autopayable_entities()
        cls._generate_non_autopayable_entities()
        cls._generate_invoices()

    @classmethod
    def tearDownClass(cls):
        cls.non_autopay_domain.delete()
        super(TestBillingAutoPay, cls).tearDownClass()

    @classmethod
    def _generate_autopayable_entities(cls):
        """
        Create account, domain and subscription linked to the autopay user that have autopay enabled
        """
        cls.autopay_account = cls.account
        cls.autopay_account.created_by_domain = cls.domain
        cls.autopay_account.save()
        cls.autopay_user_email = generator.create_arbitrary_web_user_name()
        cls.fake_card = FakeStripeCard()
        cls.fake_stripe_customer = FakeStripeCustomer(cards=[cls.fake_card])
        cls.autopay_account.update_autopay_user(cls.autopay_user_email, cls.domain)

    @classmethod
    def _generate_non_autopayable_entities(cls):
        """
        Create account, domain, and subscription linked to the autopay user, but that don't have autopay enabled
        """
        cls.non_autopay_account = generator.billing_account(
            web_user_creator=generator.create_arbitrary_web_user_name(is_dimagi=True),
            web_user_contact=cls.autopay_user_email
        )
        cls.non_autopay_domain = generator.arbitrary_domain()
        # Non-autopay subscription has same parameters as the autopayable subscription
        cheap_plan = SoftwarePlan.objects.create(name='cheap')
        cheap_product_rate = SoftwareProductRate.objects.create(monthly_fee=100, name=cheap_plan.name)
        cheap_plan_version = SoftwarePlanVersion.objects.create(
            plan=cheap_plan,
            product_rate=cheap_product_rate,
            role=Role.objects.first(),
        )
        cls.non_autopay_subscription = generator.generate_domain_subscription(
            cls.non_autopay_account,
            cls.non_autopay_domain,
            plan_version=cheap_plan_version,
            date_start=cls.subscription.date_start,
            date_end=add_months_to_date(cls.subscription.date_start, cls.subscription_length),
        )

    @classmethod
    def _generate_invoices(cls):
        """
        Create invoices for both autopayable and non-autopayable subscriptions
        """
        # invoice date is 2 months before the end of the subscription (this is arbitrary)
        invoice_date = utils.months_from_date(cls.subscription.date_start, cls.subscription_length - 2)
        tasks.calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

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
        fake_charge.return_value = StripeObject(id='transaction_id')

        original_outbox_length = len(mail.outbox)

        autopayable_invoice = Invoice.objects.filter(subscription=self.subscription)
        date_due = autopayable_invoice.first().date_due

        AutoPayInvoicePaymentHandler().pay_autopayable_invoices(date_due)
        self.assertAlmostEqual(autopayable_invoice.first().get_total(), 0)
        self.assertEqual(len(PaymentRecord.objects.all()), 1)
        self.assertEqual(len(mail.outbox), original_outbox_length + 1)

    def _create_autopay_method(self, fake_customer):
        fake_customer.__get__ = mock.Mock(return_value=self.fake_stripe_customer)
        self.payment_method = StripePaymentMethod(web_user=self.autopay_user_email,
                                                  customer_id=self.fake_stripe_customer.id)
        self.payment_method.set_autopay(self.fake_card, self.autopay_account, self.domain)
        self.payment_method.save()

    @mock.patch.object(StripePaymentMethod, 'customer')
    @mock.patch.object(Charge, 'create')
    @mock.patch.object(PaymentRecord, 'create_record')
    def test_when_create_record_fails_stripe_is_not_charged(self, fake_create_record, fake_create, fake_customer):
        fake_create_record.side_effect = Exception
        self._create_autopay_method(fake_customer)

        self.original_outbox_length = len(mail.outbox)
        self._run_autopay()
        self.assertFalse(fake_create.called)
        self._assert_no_side_effects()

    @mock.patch.object(StripePaymentMethod, 'customer')
    @mock.patch.object(Charge, 'create')
    def test_when_stripe_fails_no_payment_record_exists(self, fake_create, fake_customer):
        fake_create.side_effect = Exception
        self._create_autopay_method(fake_customer)

        self.original_outbox_length = len(mail.outbox)
        self._run_autopay()
        self._assert_no_side_effects()

    def _run_autopay(self):
        autopayable_invoice = Invoice.objects.filter(subscription=self.subscription)
        date_due = autopayable_invoice.first().date_due
        AutoPayInvoicePaymentHandler().pay_autopayable_invoices(date_due)

    def _assert_no_side_effects(self):
        self.assertEqual(PaymentRecord.objects.count(), 0)
        self.assertEqual(len(mail.outbox), self.original_outbox_length)
