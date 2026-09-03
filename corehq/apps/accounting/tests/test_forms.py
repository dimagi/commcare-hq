import datetime
import random
from decimal import Decimal
from unittest.mock import call, patch

import pytest
from dateutil.relativedelta import relativedelta
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.test import TestCase

from corehq.apps.accounting.exceptions import InvoiceError
from corehq.apps.accounting.forms import (
    AdjustBalanceForm,
    GeneratePrepaymentInvoiceForm,
    PlanContactForm,
    SubscriptionForm,
    TriggerInvoiceForm,
    WirePrepaymentForm,
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
    PaymentType,
    SoftwarePlanEdition,
    SoftwarePlanVersion,
    Subscription,
)
from corehq.apps.accounting.tasks import (
    calculate_users_in_all_domains,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from corehq.apps.accounting.tests.utils import in_days
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
                'adjustment_reason': CreditAdjustmentReason.MANUAL,
                'payment_type': PaymentType.OTHER,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        assert adjust_balance_form.is_valid()

        adjust_balance_form.adjust_balance()
        assert original_balance - adjustment_amount == self.invoice.balance

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
                'adjustment_reason': CreditAdjustmentReason.TRANSFER,
                'payment_type': PaymentType.OTHER,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        assert adjust_balance_form.is_valid()

        adjust_balance_form.adjust_balance()
        assert original_balance - adjustment_amount == self.invoice.balance
        assert original_credit_balance - adjustment_amount == sum(
            credit_line.balance
            for credit_line in CreditLine.get_credits_for_invoice(self.invoice)
        )

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
                'adjustment_reason': CreditAdjustmentReason.TRANSFER,
                'payment_type': PaymentType.OTHER,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        assert adjust_balance_form.is_valid()

        adjust_balance_form.adjust_balance()
        assert original_balance == self.invoice.balance
        assert original_credit_balance == sum(
            credit_line.balance
            for credit_line in CreditLine.get_credits_for_invoice(self.invoice)
        )


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
                'adjustment_reason': CreditAdjustmentReason.MANUAL,
                'payment_type': PaymentType.OTHER,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        assert adjust_balance_form.is_valid()

        adjust_balance_form.adjust_balance()
        assert original_balance - adjustment_amount == self.invoice.balance

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
                'adjustment_reason': CreditAdjustmentReason.TRANSFER,
                'payment_type': PaymentType.OTHER,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        assert adjust_balance_form.is_valid()

        adjust_balance_form.adjust_balance()
        assert original_balance - adjustment_amount == self.invoice.balance
        assert original_credit_balance - adjustment_amount == sum(
            credit_line.balance
            for credit_line in CreditLine.get_credits_for_customer_invoice(self.invoice)
        )

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
                'adjustment_reason': CreditAdjustmentReason.TRANSFER,
                'payment_type': PaymentType.OTHER,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        assert adjust_balance_form.is_valid()

        adjust_balance_form.adjust_balance()
        assert original_balance == self.invoice.balance
        assert original_credit_balance == sum(
            credit_line.balance
            for credit_line in CreditLine.get_credits_for_customer_invoice(self.invoice)
        )


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
            **self.shared_keywords(),
        }

        with pytest.raises(ValidationError):
            subscription_form.clean_active_accounts()

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
            **self.shared_keywords(),
        }

        with pytest.raises(ValidationError):
            subscription_form.clean_active_accounts()

    def test_form_data_create_subscription(self):
        required_args = {
            'account': self.account.id,
            'domain': self.domain.name,
            'plan_version': self.plan.id,
        }
        subscription_form = SubscriptionForm(
            subscription=None,
            account_id=self.plan.id,
            web_user=self.web_user,
        )

        with patch('corehq.apps.accounting.forms.Subscription') as subscription_cls:
            subscription_form.cleaned_data = {**required_args, **self.shared_keywords()}
            subscription_form.create_subscription()
            args, kwargs = subscription_cls.new_domain_subscription.call_args

        assert args == (
            BillingAccount.objects.get(id=self.account.id),
            self.domain.name,
            SoftwarePlanVersion.objects.get(id=self.plan.id),
        )
        assert kwargs['web_user'] == self.web_user
        assert kwargs['internal_change']
        expected = self.shared_keywords()
        expected_days = expected.pop('skip_auto_downgrade_days')
        for k, v in expected.items():
            assert kwargs[k] == v
        assert kwargs['skip_auto_downgrade_until'] == datetime.date.today() + datetime.timedelta(
            days=expected_days
        )

    def test_form_data_update_subscription(self):
        subscription = Subscription.new_domain_subscription(
            domain=self.domain.name,
            plan_version=self.plan,
            account=self.account,
        )
        subscription_form = SubscriptionForm(
            subscription=subscription,
            account_id=self.plan.id,
            web_user=self.web_user,
        )

        with patch.object(subscription, 'update_subscription') as update_subscription:
            subscription_form.cleaned_data = {**self.shared_keywords()}
            subscription_form.update_subscription()
            kwargs = update_subscription.call_args.kwargs

        assert kwargs['web_user'] == self.web_user
        expected = self.shared_keywords()
        expected_days = expected.pop('skip_auto_downgrade_days')
        for k, v in expected.items():
            assert kwargs[k] == v
        assert kwargs['skip_auto_downgrade_until'] == datetime.date.today() + datetime.timedelta(
            days=expected_days
        )

    def test_shared_keywords_computes_skip_auto_downgrade_until_from_days(self):
        subscription_form = SubscriptionForm(
            subscription=None,
            account_id=self.plan.id,
            web_user=self.web_user,
        )
        subscription_form.cleaned_data = {**self.shared_keywords(), 'skip_auto_downgrade_days': 5}

        assert subscription_form.shared_keywords['skip_auto_downgrade_until'] == (
            datetime.date.today() + datetime.timedelta(days=5)
        )

    def test_shared_keywords_blank_skip_auto_downgrade_days_means_no_expiration(self):
        subscription_form = SubscriptionForm(
            subscription=None,
            account_id=self.plan.id,
            web_user=self.web_user,
        )
        subscription_form.cleaned_data = {**self.shared_keywords(), 'skip_auto_downgrade_days': None}

        assert subscription_form.shared_keywords['skip_auto_downgrade_until'] is None

    def test_editing_subscription_prefills_skip_auto_downgrade_days_remaining(self):
        subscription = Subscription.new_domain_subscription(
            domain=self.domain.name,
            plan_version=self.plan,
            account=self.account,
        )
        subscription.skip_auto_downgrade = True
        subscription.skip_auto_downgrade_until = datetime.date.today() + datetime.timedelta(days=10)
        subscription.save()

        subscription_form = SubscriptionForm(
            subscription=subscription,
            account_id=self.account.id,
            web_user=self.web_user,
        )

        assert subscription_form.fields['skip_auto_downgrade'].initial is True
        assert subscription_form.fields['skip_auto_downgrade_days'].initial == 10

    def test_editing_subscription_with_expired_skip_auto_downgrade_unchecks_checkbox(self):
        subscription = Subscription.new_domain_subscription(
            domain=self.domain.name,
            plan_version=self.plan,
            account=self.account,
        )
        subscription.skip_auto_downgrade = True
        subscription.skip_auto_downgrade_until = datetime.date.today() - datetime.timedelta(days=3)
        subscription.save()

        subscription_form = SubscriptionForm(
            subscription=subscription,
            account_id=self.account.id,
            web_user=self.web_user,
        )

        assert subscription_form.fields['skip_auto_downgrade'].initial is False
        assert subscription_form.fields['skip_auto_downgrade_days'].initial is None

    def test_editing_subscription_with_no_expiration_leaves_skip_auto_downgrade_days_blank(self):
        subscription = Subscription.new_domain_subscription(
            domain=self.domain.name,
            plan_version=self.plan,
            account=self.account,
        )

        subscription_form = SubscriptionForm(
            subscription=subscription,
            account_id=self.account.id,
            web_user=self.web_user,
        )

        assert subscription_form.fields['skip_auto_downgrade_days'].initial is None

    @staticmethod
    def shared_keywords():
        # maps to SubscriptionForm.shared_keywords
        return {
            'date_start': datetime.date.today(),
            'date_end': datetime.date.today() + datetime.timedelta(days=7),
            'do_not_invoice': True,
            'no_invoice_reason': 'I said so',
            'do_not_email_invoice': True,
            'do_not_email_reminder': True,
            'auto_generate_credits': True,
            'skip_invoicing_if_no_feature_charges': True,
            'salesforce_contract_id': 'abc123',
            'service_type': 'SubscriptionType',
            'pro_bono_status': 'ProBonoStatus',
            'funding_source': 'FundingSource',
            'skip_auto_downgrade': True,
            'skip_auto_downgrade_reason': 'You said so',
            'skip_auto_downgrade_days': 30,
            'auto_renew': True,
        }


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
        assert invoice.date_start == self.statement_start
        assert invoice.date_end == self.statement_end

    def test_clean_previous_invoices(self):
        prev_invoice = Invoice.objects.create(
            date_start=self.statement_start,
            date_end=self.statement_end,
            subscription=self.subscription
        )
        self.init_form(self.form_data())
        self.form.full_clean()

        with pytest.raises(InvoiceError) as e:
            self.form.clean_previous_invoices(self.statement_start, self.statement_end, self.domain.name)
        assert prev_invoice.invoice_number in str(e.value)

    def test_show_testing_options(self):
        self.init_form(self.form_data(), show_testing_options=False)
        assert 'num_mobile_workers' not in self.form.fields
        assert 'num_form_submitting_workers' not in self.form.fields

        self.init_form(self.form_data(), show_testing_options=True)
        assert 'num_mobile_workers' in self.form.fields
        assert 'num_form_submitting_workers' in self.form.fields

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
        assert user_history.num_users == num_users

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
        assert user_history.num_users == num_users


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
        assert subject == expected_subject
        assert all(value in text_content for value in data.values())


def wire_prepayment_post_data(**overrides):
    """Returns the fields that the payment modal posts, with valid values."""
    data = {
        'email_to': 'jane@example.com',
        'email_cc': '',
        'prepay_date_start': '',
        'prepay_date_end': '',
        'credit_label': 'General Credits',
        'unit_cost': '10.00',
        'quantity': '1',
    }
    data.update(overrides)
    return data


class TestWirePrepaymentForm:

    def test_valid_data(self):
        date_start = datetime.date.today()
        date_end = date_start + datetime.timedelta(days=365)
        form = WirePrepaymentForm(wire_prepayment_post_data(
            email_to='jane@example.com',
            email_cc='john@example.com',
            prepay_date_start=date_start.isoformat(),
            prepay_date_end=date_end.isoformat(),
            credit_label='Annual plan',
            unit_cost='12.50',
            quantity='4',
        ))
        assert form.is_valid(), form.errors
        assert form.cleaned_data == {
            'email_to': 'jane@example.com',
            'email_cc': ['john@example.com'],
            'prepay_date_start': date_start,
            'prepay_date_end': date_end,
            'credit_label': 'Annual plan',
            'unit_cost': Decimal('12.50'),
            'quantity': 4,
            'amount': Decimal('50.00'),
            'send_date': None,
        }

    def test_amount_larger_than_an_invoice_can_hold(self):
        form = WirePrepaymentForm(wire_prepayment_post_data(unit_cost='500000.00', quantity='3'))
        assert not form.is_valid()
        assert form.errors[NON_FIELD_ERRORS] == [
            'The total prepayment amount cannot be more than $999999.99.'
        ]

    @pytest.mark.parametrize('email_cc, expected', [
        ('', []),
        ('john@example.com', ['john@example.com']),
        ('john@example.com, bob@example.com', ['john@example.com', 'bob@example.com']),
        ('john@example.com,', ['john@example.com']),
        (' john@example.com ', ['john@example.com']),
    ])
    def test_email_cc_is_cleaned_to_a_list(self, email_cc, expected):
        form = WirePrepaymentForm(wire_prepayment_post_data(email_cc=email_cc))
        assert form.is_valid(), form.errors
        assert form.cleaned_data['email_cc'] == expected

    def test_invalid_email_cc(self):
        form = WirePrepaymentForm(wire_prepayment_post_data(
            email_cc='john@example.com, bob@example, carol',
        ))
        assert not form.is_valid()
        assert form.errors['email_cc'] == [
            'The following e-mail addresses contain invalid characters, or are missing '
            'required characters: "bob@example", "carol"'
        ]

    def test_dates_default_to_today(self):
        form = WirePrepaymentForm(wire_prepayment_post_data(
            prepay_date_start='', prepay_date_end='',
        ))
        assert form.is_valid(), form.errors
        assert form.cleaned_data['prepay_date_start'] == datetime.date.today()
        assert form.cleaned_data['prepay_date_end'] == datetime.date.today()

    def test_end_date_before_start_date(self):
        start_date = datetime.date.today()
        form = WirePrepaymentForm(wire_prepayment_post_data(
            prepay_date_start=start_date.isoformat(),
            prepay_date_end=(start_date - datetime.timedelta(days=1)).isoformat(),
        ))
        assert not form.is_valid()
        assert form.errors['prepay_date_end'] == ['Prepayment end date must be after start date.']

    def test_end_date_same_as_start_date(self):
        start_date = datetime.date.today()
        form = WirePrepaymentForm(wire_prepayment_post_data(
            prepay_date_start=start_date.isoformat(),
            prepay_date_end=start_date.isoformat(),
        ))
        assert form.is_valid(), form.errors

    def test_create_invoice(self):
        date_start = datetime.date.today()
        date_end = date_start + datetime.timedelta(days=30)
        form = WirePrepaymentForm(wire_prepayment_post_data(
            email_to='jane@example.com',
            email_cc='john@example.com, bob@example.com',
            prepay_date_start=date_start.isoformat(),
            prepay_date_end=date_end.isoformat(),
            credit_label='Annual plan',
            unit_cost='2.50',
            quantity='4',
        ))
        assert form.is_valid(), form.errors

        with patch('corehq.apps.accounting.forms.DomainWireInvoiceFactory') as factory:
            form.create_invoice('test-domain')

        # The factory serializes the dates for its celery task
        assert factory.call_args == call(
            'test-domain',
            date_start=date_start.isoformat(),
            date_end=date_end.isoformat(),
            contact_emails=['jane@example.com'],
            cc_emails=['john@example.com', 'bob@example.com'],
        )
        assert factory.return_value.create_wire_credits_invoice.call_args == call(
            Decimal('10.00'), 'Annual plan', Decimal('2.50'), 4,
        )

    def test_get_error_message_labels_each_field(self):
        form = WirePrepaymentForm(wire_prepayment_post_data(email_to='nope', quantity='0'))
        assert not form.is_valid()
        assert form.get_error_message() == (
            'Email To: Enter a valid email address. '
            'Quantity: Ensure this value is greater than or equal to 1.'
        )

    def test_get_error_message_includes_non_field_errors(self):
        form = WirePrepaymentForm(wire_prepayment_post_data(unit_cost='500000.00', quantity='3'))
        assert not form.is_valid()
        assert form.get_error_message() == (
            'The total prepayment amount cannot be more than $999999.99.'
        )

    def test_get_error_message_when_valid(self):
        form = WirePrepaymentForm(wire_prepayment_post_data())
        assert form.is_valid(), form.errors
        assert form.get_error_message() == ''


class TestGeneratePrepaymentInvoiceForm(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = Domain(name='prepayment-invoice', is_active=True)
        cls.domain.save()
        cls.addClassCleanup(cls.domain.delete)

    def test_valid_project_space(self):
        form = GeneratePrepaymentInvoiceForm(
            wire_prepayment_post_data(domain=self.domain.name)
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data['domain'] == self.domain.name

    def test_unknown_project_space(self):
        form = GeneratePrepaymentInvoiceForm(
            wire_prepayment_post_data(domain='not-a-project-space')
        )
        assert not form.is_valid()
        assert form.errors['domain'] == [
            "Project space 'not-a-project-space' was not found."
        ]

    def test_get_error_message_includes_the_project_space(self):
        form = GeneratePrepaymentInvoiceForm(
            wire_prepayment_post_data(domain='not-a-project-space', quantity='0')
        )
        assert not form.is_valid()
        assert form.get_error_message() == (
            'Quantity: Ensure this value is greater than or equal to 1. '
            "Project Space: Project space 'not-a-project-space' was not found."
        )


def scheduled_prepayment_post_data(**overrides):
    data = {
        'email_to': 'billing@example.com',
        'email_cc': 'ap@example.com',
        'credit_label': '12 month prepayment',
        'unit_cost': '1000.00',
        'quantity': 12,
        'amount': '12000.00',
        'prepay_date_start': '2027-01-01',
        'prepay_date_end': '2028-01-01',
        'send_date': in_days(90).isoformat(),
    }
    data.update(overrides)
    return data


class TestScheduledPrepaymentForm:
    def test_valid_data(self):
        date_start = datetime.date.today()
        date_end = date_start + datetime.timedelta(days=365)
        form = WirePrepaymentForm(scheduled_prepayment_post_data(
            email_to='billing@example.com',
            email_cc='ap@example.com',
            prepay_date_start=date_start.isoformat(),
            prepay_date_end=date_end.isoformat(),
            credit_label='12 month prepayment',
            unit_cost='1000.00',
            quantity='12',
        ))
        assert form.is_valid(), form.errors
        assert form.cleaned_data == {
            'email_to': 'billing@example.com',
            'email_cc': ['ap@example.com'],
            'credit_label': '12 month prepayment',
            'unit_cost': Decimal(1000.00),
            'quantity': 12,
            'amount': Decimal(12000.00),
            'prepay_date_start': date_start,
            'prepay_date_end': date_end,
            'send_date': in_days(90),
        }

    @pytest.mark.parametrize('days_from_today', [
        (-1),  # yesterday
        (0),  # today
    ])
    def test_invalid_send_date(self, days_from_today):
        form = WirePrepaymentForm(
            scheduled_prepayment_post_data(send_date=in_days(days_from_today).isoformat())
        )

        assert not form.is_valid()
        assert form.errors['send_date'] == [
            'The send date must be in the future.'
        ]

    def test_accepts_a_send_date_of_tomorrow(self):
        form = WirePrepaymentForm(scheduled_prepayment_post_data(send_date=in_days(1).isoformat()))

        assert form.is_valid(), form.errors

    def test_accepts_a_missing_send_date(self):
        """A blank send date generates the invoice now instead of scheduling it."""
        form = WirePrepaymentForm(scheduled_prepayment_post_data(send_date=''))

        assert form.is_valid(), form.errors
        assert form.cleaned_data['send_date'] is None

    def test_save_generates_the_invoice_when_no_send_date(self):
        form = WirePrepaymentForm(scheduled_prepayment_post_data(send_date=''))
        assert form.is_valid(), form.errors

        with patch.object(WirePrepaymentForm, 'create_invoice') as create_invoice:
            assert form.save('test-domain', None) is None

        assert create_invoice.call_args == call('test-domain')

    def test_save_schedules_the_invoice_when_given_a_send_date(self):
        form = WirePrepaymentForm(scheduled_prepayment_post_data())
        assert form.is_valid(), form.errors
        couch_user = object()

        with patch(
            'corehq.apps.accounting.forms.Subscription.get_active_subscription_by_domain',
            return_value='a subscription',
        ), patch.object(WirePrepaymentForm, 'create_scheduled_invoice') as create_scheduled:
            form.save('test-domain', couch_user)

        assert create_scheduled.call_args == call('test-domain', 'a subscription', couch_user)

    def test_save_requires_an_active_subscription_to_schedule(self):
        form = WirePrepaymentForm(scheduled_prepayment_post_data())
        assert form.is_valid(), form.errors

        with patch(
            'corehq.apps.accounting.forms.Subscription.get_active_subscription_by_domain',
            return_value=None,
        ):
            with pytest.raises(InvoiceError, match='no active subscription'):
                form.save('test-domain', None)

    def test_rejects_credit_label_that_is_too_long(self):
        form = WirePrepaymentForm(scheduled_prepayment_post_data(credit_label='x' * 257))

        assert not form.is_valid()
        assert form.errors['credit_label'] == [
            'The credit label must be 256 characters or fewer.'
        ]

    def test_accepts_a_credit_label_at_the_limit(self):
        form = WirePrepaymentForm(scheduled_prepayment_post_data(credit_label='x' * 256))

        assert form.is_valid(), form.errors
