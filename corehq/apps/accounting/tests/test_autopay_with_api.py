from django.core import mail

from django_prbac.models import Role
import stripe

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
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from django.db import transaction
from unittest import SkipTest
from django.conf import settings
from unittest.mock import patch
import uuid


class TestBillingAutoPay(BaseInvoiceTestCase):

    @classmethod
    def setUpClass(cls):
        # Dependabot-created PRs do not have access to secrets.
        # We skip test so the tests do not fail when dependabot creates new PR for dependency upgrades.
        # Or for developers running tests locally if they do not have stripe API key in their localsettings.
        if not settings.STRIPE_PRIVATE_KEY:
            raise SkipTest("Stripe API Key not set")
        super(TestBillingAutoPay, cls).setUpClass()
        cls._generate_autopayable_entities()
        cls._generate_non_autopayable_entities()
        cls._generate_invoices()

    @classmethod
    def _generate_autopayable_entities(cls):
        """
        Create account, domain and subscription linked to the autopay user that have autopay enabled
        """
        cls.autopay_account = cls.account
        cls.autopay_account.created_by_domain = cls.domain
        cls.autopay_account.save()
        web_user = generator.arbitrary_user(domain_name=cls.domain.name, is_active=True, is_webuser=True)
        cls.autopay_user_email = web_user.email
        cls.stripe_customer = stripe.Customer.create(email=cls.autopay_user_email)
        cls.addClassCleanup(cls.stripe_customer.delete)
        cls.payment_method = StripePaymentMethod(web_user=cls.autopay_user_email,
                                                customer_id=cls.stripe_customer.id)
        cls.card = cls.payment_method.create_card('tok_visa', cls.autopay_account, None)
        cls.payment_method.set_autopay(cls.card, cls.autopay_account, cls.domain)
        cls.payment_method.save()
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
        cls.addClassCleanup(cls.non_autopay_domain.delete)
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

    def test_get_autopayable_invoices(self):
        """
        Invoice.autopayable_invoices() should return invoices that can be automatically paid
        """
        autopayable_invoice = Invoice.objects.filter(subscription=self.subscription)
        date_due = autopayable_invoice.first().date_due

        autopayable_invoices = Invoice.autopayable_invoices(date_due)

        self.assertCountEqual(autopayable_invoices, autopayable_invoice)

    def test_get_autopayable_invoices_returns_nothing(self):
        """
        Invoice.autopayable_invoices() should not return invoices if the customer does not have an autopay method
        """
        not_autopayable_invoice = Invoice.objects.filter(subscription=self.non_autopay_subscription)
        date_due = not_autopayable_invoice.first().date_due
        autopayable_invoices = Invoice.autopayable_invoices(date_due)
        self.assertCountEqual(autopayable_invoices, [])

    # Keys for idempotent requests can only be used with the same parameters they were first used with.
    # So introduce randomness in idempotency key to avoid clashes
    @patch('corehq.apps.accounting.models.Invoice.invoice_number', str(uuid.uuid4()))
    def test_pay_autopayable_invoices(self):
        original_outbox_length = len(mail.outbox)
        autopayable_invoice = Invoice.objects.filter(subscription=self.subscription).first()
        date_due = autopayable_invoice.date_due

        AutoPayInvoicePaymentHandler().pay_autopayable_invoices(date_due)

        self.assertAlmostEqual(autopayable_invoice.get_total(), 0)
        self.assertEqual(len(PaymentRecord.objects.all()), 1)
        self.assertEqual(len(mail.outbox), original_outbox_length + 1)

    # Keys for idempotent requests can only be used with the same parameters they were first used with.
    # So introduce randomness in idempotency key to avoid clashes
    @patch('corehq.apps.accounting.models.Invoice.invoice_number', str(uuid.uuid4()))
    def test_double_charge_is_prevented_and_only_one_payment_record_created(self):
        self.original_outbox_length = len(mail.outbox)
        invoice = Invoice.objects.get(subscription=self.subscription)
        balance = invoice.balance
        self._run_autopay()
        # Add balance to the same invoice so it gets paid again
        invoice = Invoice.objects.get(subscription=self.subscription)
        invoice.balance = balance
        invoice.save()
        # Run autopay again to test no double charge
        with transaction.atomic(), self.assertLogs(level='ERROR') as log_cm:
            self._run_autopay()
            self.assertIn("[BILLING] [Autopay] Attempt to double charge invoice", "\n".join(log_cm.output))
        self.assertEqual(len(PaymentRecord.objects.all()), 1)
        self.assertEqual(len(mail.outbox), self.original_outbox_length + 1)

    def _run_autopay(self):
        autopayable_invoice = Invoice.objects.filter(subscription=self.subscription)
        date_due = autopayable_invoice.first().date_due
        AutoPayInvoicePaymentHandler().pay_autopayable_invoices(date_due)
