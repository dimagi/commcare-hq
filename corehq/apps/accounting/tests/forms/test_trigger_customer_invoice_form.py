# 17 Tests, 27.769s

import datetime
from django.test import TestCase, SimpleTestCase
from unittest import mock

from corehq.apps.accounting.forms import TriggerCustomerInvoiceForm
from corehq.apps.accounting.exceptions import InvoiceError
from corehq.apps.accounting.tests import generator

from corehq.apps.domain.models import Domain
from corehq.apps.accounting.models import BillingAccount, \
    InvoicingPlan, CustomerInvoice, Subscription, DomainUserHistory


def create_form(month=1,
        year=2020,
        customer_account='Some Account',
        num_users=10,
        overwrite_user_counts=False,
        show_testing_options=False):

    data = {
        'month': month,
        'year': year,
        'customer_account': customer_account,
        'num_users': num_users,
        'overwrite_user_counts': overwrite_user_counts,
    }

    return TriggerCustomerInvoiceForm(data, show_testing_options=show_testing_options)


class TestTriggerCustomerInvoiceFormValidity(SimpleTestCase):
    TESTING_FIELDS = {'num_users', 'overwrite_user_counts'}

    def test_has_all_details_is_valid_form(self):
        form = create_form()
        self.assertTrue(form.is_valid())

    def test_missing_month_is_invalid(self):
        form = create_form(month=None)
        self.assertFalse(form.is_valid())

    def test_missing_year_is_invalid(self):
        form = create_form(year=None)
        self.assertFalse(form.is_valid())

    def test_missing_billing_account_is_invalid(self):
        form = create_form(customer_account=None)
        self.assertFalse(form.is_valid())

    def test_current_invoice_periods_are_not_valid(self):
        current_date = datetime.date(2020, 1, 10)
        form = create_form(month=1, year=2020)
        with mock.patch('corehq.apps.accounting.forms.datetime') as mock_datetime:
            mock_datetime.date.today.return_value = current_date
            self.assertFalse(form.is_valid())
            self.assertIn('Statement period must be in the past', str(form.errors))

    def test_if_testing_options_are_enabled_then_it_displays_test_fields(self):
        form = create_form(show_testing_options=True)
        self.assertTrue(self.TESTING_FIELDS.issubset(set(form.fields)))

    def test_if_testing_options_are_disabled_then_it_hides_test_fields(self):
        form = create_form(show_testing_options=False)
        self.assertTrue(self.TESTING_FIELDS.isdisjoint(set(form.fields)))


class TestTriggerCustomerInvoice(TestCase):
    def setUp(self):
        self.billing_account_obj = self.create_billing_account()
        self.month = 10
        self.year = 2020
        self.start_date = datetime.date(self.year, self.month, 1)
        self.end_date = datetime.date(self.year, self.month, 31)

        self.domains = []

    def tearDown(self):
        for domain_obj in self.domains:
            domain_obj.delete()

    def create_form(self, **kwargs):
        if 'customer_account' not in kwargs:
            kwargs['customer_account'] = self.billing_account_obj.name
        kwargs['month'] = self.month
        kwargs['year'] = self.year
        return create_form(**kwargs)

    def create_billing_account(self, name=None, invoicing_plan=None):
        self.account = BillingAccount.create_account_for_domain('test_domain', created_by='TEST')

        dirty = False
        if name:
            self.account.name = name
            dirty = True

        if invoicing_plan:
            self.account.invoicing_plan = invoicing_plan
            dirty = True

        if dirty:
            self.account.save()

        return self.account

    def create_invoice(self):
        invoice = CustomerInvoice(account=self.billing_account_obj,
                date_start=self.start_date, date_end=self.end_date)
        invoice.save()
        subscription, _ = self.create_subscription()
        invoice.subscriptions.add(subscription)
        return invoice

    def create_subscription(self, domain='test_domain'):
        domain_obj = Domain(name=domain, is_active=True)
        domain_obj.save()
        self.domains.append(domain_obj)

        plan = generator.subscribable_plan_version()
        subscription_obj = Subscription.new_domain_subscription(self.billing_account_obj, domain,
                plan, date_start=self.start_date)

        return (subscription_obj, domain_obj)

    def test_if_billing_account_is_invalid_throws_error(self):
        form = self.create_form(customer_account='Missing Account')
        with self.assertRaises(InvoiceError) as context:
            form.trigger_customer_invoice()

        self.assertEqual(str(context.exception),
                'There is no Billing Account associated with Missing Account')

    def test_if_yearly_account_billed_midway_throws_error(self):
        account_obj = self.create_billing_account(invoicing_plan=InvoicingPlan.YEARLY)
        form = self.create_form(customer_account=account_obj.name, month=6)

        with self.assertRaises(InvoiceError) as context:
            form.trigger_customer_invoice()

        self.assertIn('is set to be invoiced yearly, and you may not invoice in this month.'
                ' You must select December in the year for which'
                ' you are triggering an annual invoice.', str(context.exception))

    def test_if_quarterly_account_billed_non_quarter_throws_error(self):
        account_obj = self.create_billing_account(invoicing_plan=InvoicingPlan.QUARTERLY)
        form = self.create_form(customer_account=account_obj.name, month=2)

        with self.assertRaises(InvoiceError) as context:
            form.trigger_customer_invoice()

        self.assertIn('is set to be invoiced quarterly, and you may not invoice in this month.'
                ' You must select the last month of a quarter'
                ' to trigger a quarterly invoice.', str(context.exception))

    def test_if_invoice_already_exists_throws_error(self):
        self.create_invoice()
        form = self.create_form()
        with self.assertRaises(InvoiceError) as context:
            form.trigger_customer_invoice()

        self.assertIn('Invoices exist that were already generated'
        ' with this same criteria.', str(context.exception))

    def test_testing_options_create_user_totals(self):
        _, domain_obj = self.create_subscription()
        form = self.create_form(show_testing_options=True, num_users=130)

        form.trigger_customer_invoice()

        user_count = DomainUserHistory.objects.get(domain=domain_obj)
        self.assertEqual(user_count.num_users, 130)

    def test_testing_options_create_user_totals_for_multiple_domains(self):
        _, domain1_obj = self.create_subscription(domain='domain1')
        _, domain2_obj = self.create_subscription(domain='domain2')

        form = self.create_form(show_testing_options=True, num_users=50)

        form.trigger_customer_invoice()

        domain1_user_count = DomainUserHistory.objects.get(domain=domain1_obj)
        domain2_user_count = DomainUserHistory.objects.get(domain=domain2_obj)
        self.assertEqual(domain1_user_count.num_users, 50)
        self.assertEqual(domain2_user_count.num_users, 50)

    def test_will_not_overwrite_existing_user_totals(self):
        _, domain_obj = self.create_subscription()
        DomainUserHistory.objects.create(domain=domain_obj, record_date=self.end_date, num_users=40)

        form = self.create_form(show_testing_options=True, num_users=50,
                overwrite_user_counts=False)

        form.trigger_customer_invoice()

        user_count = DomainUserHistory.objects.get(domain=domain_obj)
        self.assertEqual(user_count.num_users, 40)

    def test_with_overwrite_flag_will_overwrite_user_totals(self):
        _, domain_obj = self.create_subscription()
        DomainUserHistory.objects.create(domain=domain_obj, record_date=self.end_date, num_users=40)

        form = self.create_form(show_testing_options=True, num_users=50, overwrite_user_counts=True)

        form.trigger_customer_invoice()

        user_count = DomainUserHistory.objects.get(domain=domain_obj)
        self.assertEqual(user_count.num_users, 50)

    def test_when_some_domains_have_existing_user_totals_will_only_create_missing_totals(self):
        _, domain1_obj = self.create_subscription(domain='domain1')
        _, domain2_obj = self.create_subscription(domain='domain2')
        DomainUserHistory.objects.create(domain=domain1_obj, record_date=self.end_date,
                num_users=40)

        form = self.create_form(show_testing_options=True, num_users=50,
                overwrite_user_counts=False)

        form.trigger_customer_invoice()

        domain1_user_count = DomainUserHistory.objects.get(domain=domain1_obj)
        domain2_user_count = DomainUserHistory.objects.get(domain=domain2_obj)
        self.assertEqual(domain1_user_count.num_users, 40)
        self.assertEqual(domain2_user_count.num_users, 50)

    def test_zero_num_users_is_respected(self):
        _, domain_obj = self.create_subscription()
        form = self.create_form(show_testing_options=True, num_users=0, overwrite_user_counts=True)

        form.trigger_customer_invoice()

        user_count = DomainUserHistory.objects.get(domain=domain_obj)
        self.assertEqual(user_count.num_users, 0)
