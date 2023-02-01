import datetime
import random

from django.core.exceptions import ValidationError

from dateutil.relativedelta import relativedelta

from corehq.apps.accounting.forms import AdjustBalanceForm, SubscriptionForm
from corehq.apps.accounting.models import (
    BillingAccount,
    CreditAdjustmentReason,
    CreditLine,
    CustomerInvoice,
    DefaultProductPlan,
    Invoice,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.accounting.tasks import (
    calculate_users_in_all_domains,
    generate_invoices_based_on_date,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser


class TestAdjustBalanceForm(BaseInvoiceTestCase):

    def setUp(self):
        super(TestAdjustBalanceForm, self).setUp()
        invoice_date = self.subscription.date_start + relativedelta(months=1)
        calculate_users_in_all_domains(datetime.date(invoice_date.year, invoice_date.month, 1))
        generate_invoices_based_on_date(invoice_date)
        self.invoice = Invoice.objects.first()

    def tearDown(self):
        super(TestAdjustBalanceForm, self).tearDown()

    def test_manual_adjustment(self):
        original_balance = self.invoice.balance
        adjustment_amount = random.randint(1, 5)

        adjust_balance_form = AdjustBalanceForm(
            self.invoice,
            {
                'adjustment_type': 'credit',
                'custom_amount': adjustment_amount,
                'method': CreditAdjustmentReason.MANUAL,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        self.assertTrue(adjust_balance_form.is_valid())

        adjust_balance_form.adjust_balance()
        self.assertEqual(original_balance - adjustment_amount, self.invoice.balance)

    def test_transfer_credit_with_credit(self):
        original_credit_balance = random.randint(5, 10)
        CreditLine.add_credit(
            original_credit_balance,
            account=self.subscription.account,
            subscription=self.subscription,
        )
        original_balance = self.invoice.balance
        adjustment_amount = random.randint(1, 5)

        adjust_balance_form = AdjustBalanceForm(
            self.invoice,
            {
                'adjustment_type': 'credit',
                'custom_amount': adjustment_amount,
                'method': CreditAdjustmentReason.TRANSFER,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        self.assertTrue(adjust_balance_form.is_valid())

        adjust_balance_form.adjust_balance()
        self.assertEqual(original_balance - adjustment_amount, self.invoice.balance)
        self.assertEqual(original_credit_balance - adjustment_amount, sum(
            credit_line.balance
            for credit_line in CreditLine.get_credits_for_invoice(self.invoice)
        ))

    def test_transfer_credit_without_credit(self):
        original_credit_balance = 0
        CreditLine.add_credit(
            original_credit_balance,
            account=self.subscription.account,
            subscription=self.subscription,
        )
        original_balance = self.invoice.balance
        adjustment_amount = random.randint(1, 5)

        adjust_balance_form = AdjustBalanceForm(
            self.invoice,
            {
                'adjustment_type': 'credit',
                'custom_amount': adjustment_amount,
                'method': CreditAdjustmentReason.TRANSFER,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        self.assertTrue(adjust_balance_form.is_valid())

        adjust_balance_form.adjust_balance()
        self.assertEqual(original_balance, self.invoice.balance)
        self.assertEqual(original_credit_balance, sum(
            credit_line.balance
            for credit_line in CreditLine.get_credits_for_invoice(self.invoice)
        ))


class TestAdjustBalanceFormForCustomerAccount(BaseInvoiceTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestAdjustBalanceFormForCustomerAccount, cls).setUpClass()
        cls.account.is_customer_billing_account = True
        cls.account.save()

    def setUp(self):
        super(TestAdjustBalanceFormForCustomerAccount, self).setUp()
        invoice_date = self.subscription.date_start + relativedelta(months=1)
        calculate_users_in_all_domains(datetime.date(invoice_date.year, invoice_date.month, 1))
        generate_invoices_based_on_date(invoice_date)
        self.invoice = CustomerInvoice.objects.first()

    def tearDown(self):
        super(TestAdjustBalanceFormForCustomerAccount, self).tearDown()

    def test_manual_adjustment(self):
        original_balance = self.invoice.balance
        adjustment_amount = random.randint(1, 5)

        adjust_balance_form = AdjustBalanceForm(
            self.invoice,
            {
                'adjustment_type': 'credit',
                'custom_amount': adjustment_amount,
                'method': CreditAdjustmentReason.MANUAL,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        self.assertTrue(adjust_balance_form.is_valid())

        adjust_balance_form.adjust_balance()
        self.assertEqual(original_balance - adjustment_amount, self.invoice.balance)

    def test_transfer_credit_with_credit(self):
        original_credit_balance = random.randint(5, 10)
        CreditLine.add_credit(
            original_credit_balance,
            account=self.account
        )
        original_balance = self.invoice.balance
        adjustment_amount = random.randint(1, 5)

        adjust_balance_form = AdjustBalanceForm(
            self.invoice,
            {
                'adjustment_type': 'credit',
                'custom_amount': adjustment_amount,
                'method': CreditAdjustmentReason.TRANSFER,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        self.assertTrue(adjust_balance_form.is_valid())

        adjust_balance_form.adjust_balance()
        self.assertEqual(original_balance - adjustment_amount, self.invoice.balance)
        self.assertEqual(original_credit_balance - adjustment_amount, sum(
            credit_line.balance
            for credit_line in CreditLine.get_credits_for_customer_invoice(self.invoice)
        ))

    def test_transfer_credit_without_credit(self):
        original_credit_balance = 0
        CreditLine.add_credit(
            original_credit_balance,
            account=self.account
        )
        original_balance = self.invoice.balance
        adjustment_amount = random.randint(1, 5)

        adjust_balance_form = AdjustBalanceForm(
            self.invoice,
            {
                'adjustment_type': 'credit',
                'custom_amount': adjustment_amount,
                'method': CreditAdjustmentReason.TRANSFER,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        self.assertTrue(adjust_balance_form.is_valid())

        adjust_balance_form.adjust_balance()
        self.assertEqual(original_balance, self.invoice.balance)
        self.assertEqual(original_credit_balance, sum(
            credit_line.balance
            for credit_line in CreditLine.get_credits_for_customer_invoice(self.invoice)
        ))


class TestSubscriptionForm(BaseAccountingTest):

    def setUp(self):
        super(TestSubscriptionForm, self).setUp()

        self.domain = Domain(
            name="test-sub-form",
            is_active=True
        )
        self.domain.save()
        self.domain2 = Domain(
            name="test-sub-form-2",
            is_active=True
        )
        self.domain2.save()

        self.web_user = WebUser.create(
            self.domain.name, generator.create_arbitrary_web_user_name(), 'testpwd', None, None
        )

        self.account = BillingAccount.get_or_create_account_by_domain(
            self.domain.name, created_by=self.web_user.username
        )[0]
        self.account.save()
        self.customer_account = BillingAccount.get_or_create_account_by_domain(
            self.domain2.name, created_by=self.web_user.username
        )[0]
        self.customer_account.is_customer_billing_account = True
        self.customer_account.save()

        self.plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        self.customer_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        self.customer_plan.plan.is_customer_software_plan = True

    def tearDown(self):
        self.domain.delete()
        self.domain2.delete()
        super(TestSubscriptionForm, self).tearDown()

    def test_regular_plan_not_added_to_customer_account(self):
        subscription = Subscription.new_domain_subscription(
            domain=self.domain.name,
            plan_version=self.plan,
            account=self.account
        )
        subscription_form = SubscriptionForm(
            subscription=subscription,
            account_id=self.account.id,
            web_user=self.web_user,
        )
        subscription_form.cleaned_data = {
            'active_accounts': self.customer_account.id,
            'start_date': datetime.date.today(),
            'end_date': None,
            'do_not_invoice': None,
            'no_invoice_reason': None,
            'do_not_email_invoice': None,
            'do_not_email_reminder': None,
            'auto_generate_credits': None,
            'skip_invoicing_if_no_feature_charges': None,
            'salesforce_contract_id': None,
            'service_type': None,
            'pro_bono_status': None,
            'funding_source': None,
            'skip_auto_downgrade': None,
            'skip_auto_downgrade_reason': None
        }

        self.assertRaises(ValidationError, lambda: subscription_form.clean_active_accounts())

    def test_customer_plan_not_added_to_regular_account(self):
        subscription = Subscription.new_domain_subscription(
            domain=self.domain.name,
            plan_version=self.customer_plan,
            account=self.customer_account
        )
        subscription_form = SubscriptionForm(
            subscription=subscription,
            account_id=self.customer_plan.id,
            web_user=self.web_user,
        )
        subscription_form.cleaned_data = {
            'active_accounts': self.account.id,
            'start_date': datetime.date.today(),
            'end_date': None,
            'do_not_invoice': None,
            'no_invoice_reason': None,
            'do_not_email_invoice': None,
            'do_not_email_reminder': None,
            'auto_generate_credits': None,
            'skip_invoicing_if_no_feature_charges': None,
            'salesforce_contract_id': None,
            'service_type': None,
            'pro_bono_status': None,
            'funding_source': None,
            'skip_auto_downgrade': None,
            'skip_auto_downgrade_reason': None
        }

        self.assertRaises(ValidationError, lambda: subscription_form.clean_active_accounts())
