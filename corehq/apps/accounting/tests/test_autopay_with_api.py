from django.core import mail

from django_prbac.models import Role
import stripe

from dimagi.utils.dates import add_months_to_date

from corehq.apps.accounting import utils
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

    def setUp(self):
        # Dependabot-created PRs do not have access to secrets.
        # We skip test so the tests do not fail when dependabot creates new PR for dependency upgrades.
        # Or for developers running tests locally if they do not have stripe API key in their localsettings.
        if not settings.STRIPE_PRIVATE_KEY:
            raise SkipTest("Stripe API Key not set")
        super().setUp()
        self._generate_autopayable_entities()
        self._generate_non_autopayable_entities()

        # invoice date is 2 months before the end of the subscription (this is arbitrary)
        invoice_date = utils.months_from_date(self.subscription.date_start, self.subscription_length - 2)
        self.create_invoices(invoice_date)

    def _generate_autopayable_entities(self):
        """
        Create account, domain and subscription linked to the autopay user that have autopay enabled
        """
        self.autopay_account = self.account
        self.autopay_account.created_by_domain = self.domain
        self.autopay_account.save()
        web_user = generator.arbitrary_user(domain_name=self.domain.name, is_active=True, is_webuser=True)
        self.autopay_user_email = web_user.email
        self.stripe_customer = stripe.Customer.create(email=self.autopay_user_email)
        self.addClassCleanup(self.stripe_customer.delete)
        self.payment_method = StripePaymentMethod(web_user=self.autopay_user_email,
                                                customer_id=self.stripe_customer.id)
        self.card = self.payment_method.create_card('tok_visa', self.autopay_account, None)
        self.payment_method.set_autopay(self.card, self.autopay_account, self.domain)
        self.payment_method.save()
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
        self.addClassCleanup(self.non_autopay_domain.delete)
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
