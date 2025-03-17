import datetime
import random
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from dateutil.relativedelta import relativedelta

from corehq.apps.accounting.exceptions import InvoiceError
from corehq.apps.accounting.forms import (
    AdjustBalanceForm,
    PlanContactForm,
    SubscriptionForm,
    TriggerInvoiceForm,
)
from corehq.apps.accounting.models import (
    BillingAccount,
    CreditAdjustmentReason,
    CreditLine,
    CustomerInvoice,
    DefaultProductPlan,
    DomainUserHistory,
    FormSubmittingMobileWorkerHistory,
    Invoice,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.accounting.tasks import (
    calculate_users_in_all_domains,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.util.dates import get_first_last_days


class TestAdjustBalanceForm(BaseInvoiceTestCase):

    def setUp(self):
        super(TestAdjustBalanceForm, self).setUp()
        invoice_date = self.subscription.date_start + relativedelta(months=1)
        self.create_invoices(datetime.date(invoice_date.year, invoice_date.month, 1))
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

    def setUp(self):
        super().setUp()
        self.account.is_customer_billing_account = True
        self.account.save()
        invoice_date = self.subscription.date_start + relativedelta(months=1)
        self.create_invoices(datetime.date(invoice_date.year, invoice_date.month, 1))
        self.invoice = CustomerInvoice.objects.first()

    def tearDown(self):
        super().tearDown()

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


class TestTriggerInvoiceForm(BaseInvoiceTestCase):

    def setUp(self):
        super().setUp()
        statement_period = self.subscription.date_start + relativedelta(months=1)
        self.statement_start, self.statement_end = get_first_last_days(
            statement_period.year, statement_period.month
        )
        calculate_users_in_all_domains(self.statement_end + datetime.timedelta(days=1))

    def init_form(self, form_data, show_testing_options=False):
        self.form = TriggerInvoiceForm(
            data=form_data,
            show_testing_options=show_testing_options
        )

    def form_data(self, **kwargs):
        form_data = {
            'month': str(self.statement_start.month),
            'year': str(self.statement_start.year),
            'domain': self.domain.name,
        }
        form_data.update({k: str(v) for k, v in kwargs.items()})
        return form_data

    def test_trigger_invoice(self):
        self.init_form(self.form_data())
        self.form.full_clean()
        self.form.trigger_invoice()

        invoice = self.subscription.invoice_set.latest('date_created')
        self.assertEqual(invoice.date_start, self.statement_start)
        self.assertEqual(invoice.date_end, self.statement_end)

    def test_clean_previous_invoices(self):
        prev_invoice = Invoice.objects.create(
            date_start=self.statement_start,
            date_end=self.statement_end,
            subscription=self.subscription
        )
        self.init_form(self.form_data())
        self.form.full_clean()

        with self.assertRaises(InvoiceError) as e:
            self.form.clean_previous_invoices(self.statement_start, self.statement_end, self.domain.name)
        self.assertIn(prev_invoice.invoice_number, str(e.exception))

    def test_show_testing_options(self):
        self.init_form(self.form_data(), show_testing_options=False)
        self.assertNotIn('num_mobile_workers', self.form.fields)
        self.assertNotIn('num_form_submitting_workers', self.form.fields)

        self.init_form(self.form_data(), show_testing_options=True)
        self.assertIn('num_mobile_workers', self.form.fields)
        self.assertIn('num_form_submitting_workers', self.form.fields)

    def test_num_mobile_workers(self):
        num_users = 10
        self.init_form(
            self.form_data(num_mobile_workers=num_users),
            show_testing_options=True
        )
        self.form.full_clean()
        self.form.trigger_invoice()

        user_history = DomainUserHistory.objects.get(
            domain=self.domain.name, record_date=self.statement_end
        )
        self.assertEqual(user_history.num_users, num_users)

    def test_num_form_submitting_mobile_workers(self):
        num_users = 5
        self.init_form(
            self.form_data(num_form_submitting_workers=num_users),
            show_testing_options=True
        )
        self.form.full_clean()
        self.form.trigger_invoice()

        user_history = FormSubmittingMobileWorkerHistory.objects.get(
            domain=self.domain.name, record_date=self.statement_end
        )
        self.assertEqual(user_history.num_users, num_users)


class TestPlanContactForm(TestCase):
    def setUp(self):
        super().setUp()
        self.domain = generator.arbitrary_domain()
        self.addCleanup(self.domain.delete)
        self.web_user = generator.arbitrary_user(self.domain.name, is_webuser=True)

    @patch('corehq.apps.accounting.forms.send_html_email_async')
    def test_send_message(self, mock_send):
        data = {
            'name': 'Nelson Muntz',
            'company_name': 'Springfield Elementary',
            'message': 'Haw haw.'
        }
        form = PlanContactForm(self.domain.name, self.web_user, data=data)
        form.full_clean()

        request_type = 'Testy McTestFace'
        form.send_message(request_type)
        mock_send.delay.assert_called_once()

        args = mock_send.delay.call_args[0]
        subject = args[0]
        text_content = args[3]

        expected_subject = f'[{request_type}] {self.domain.name}'
        self.assertEqual(subject, expected_subject)
        self.assertTrue(all(value in text_content for value in data.values()))
