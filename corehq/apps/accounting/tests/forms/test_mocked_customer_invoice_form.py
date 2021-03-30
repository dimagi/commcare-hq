# 13 Tests, 0.424s

import datetime
from unittest import mock
from unittest.mock import patch
from django.test import TestCase

from corehq.apps.accounting.models import BillingAccount, \
    InvoicingPlan, CustomerInvoice, DomainUserHistory
from corehq.apps.accounting.exceptions import InvoiceError
from corehq.apps.accounting.forms import TriggerCustomerInvoiceForm


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


class TestMockCustomerInvoiceForm(TestCase):
    def setUp(self):
        self.billing_account_obj = BillingAccount()
        self.domains = []
        self.month = 10
        self.year = 2020
        self.start_date = datetime.date(self.year, self.month, 1)
        self.end_date = datetime.date(self.year, self.month, 31)

        self.create_mocks()

    def create_mocks(self):
        self.billing_account_obj.get_active_domains = mock.MagicMock(return_value=self.domains)

        patcher = patch.object(BillingAccount.objects, 'get')
        self.billing_account_get = patcher.start()
        self.billing_account_get.return_value = self.billing_account_obj
        self.addCleanup(patcher.stop)

        # Reverse mocked out because it takes ~1 second to generate the lookup table
        reverse_patcher = patch('corehq.apps.accounting.forms.reverse', return_value='some.url')
        reverse_patcher.start()
        self.addCleanup(reverse_patcher.stop)

    def create_form(self, **kwargs):
        kwargs['month'] = self.month
        kwargs['year'] = self.year
        return create_form(**kwargs)

    def test_if_billing_account_is_invalid_throws_error(self):
        form = self.create_form(customer_account='Missing Account')
        self.billing_account_get.side_effect = BillingAccount.DoesNotExist  # Expect get to throw

        with self.assertRaises(InvoiceError) as context:
            form.trigger_customer_invoice()

        self.assertEqual(str(context.exception),
                'There is no Billing Account associated with Missing Account')

    def test_if_yearly_account_is_billed_midway_throws_error(self):
        self.billing_account_obj.invoicing_plan = InvoicingPlan.YEARLY

        form = self.create_form(month=6)
        with self.assertRaises(InvoiceError) as context:
            form.trigger_customer_invoice()

        self.assertIn('is set to be invoiced yearly, and you may not invoice in this month.'
            ' You must select December in the year for which'
            ' you are triggering an annual invoice.', str(context.exception))

    def test_if_quarterly_account_billed_non_quarterly_throws_error(self):
        self.billing_account_obj.invoicing_plan = InvoicingPlan.QUARTERLY

        form = self.create_form(month=2)
        with self.assertRaises(InvoiceError) as context:
            form.trigger_customer_invoice()

        self.assertIn('is set to be invoiced quarterly, and you may not invoice in this month.'
            ' You must select the last month of a quarter'
            ' to trigger a quarterly invoice.', str(context.exception))

    @patch.object(CustomerInvoice, 'get_account_invoices_between_dates')
    def test_if_invoice_already_exists_throws_error(self, get_invoices):
        form = self.create_form()

        get_invoices.return_value = [CustomerInvoice(id=5)]
        with self.assertRaises(InvoiceError) as context:
            form.trigger_customer_invoice()

        self.assertIn('Invoices exist that were already generated'
            ' with this same criteria.', str(context.exception))


class TestMockCustomerInvoiceFormUserCounts(TestMockCustomerInvoiceForm):
    def create_mocks(self):
        super().create_mocks()
        user_history_patcher = patch.object(DomainUserHistory,
            'set_domain_user_count_during_period')
        self.set_user_count = user_history_patcher.start()
        self.addCleanup(user_history_patcher.stop)

    def test_testing_options_create_user_totals(self):
        self.domains.append('test_domain')

        form = self.create_form(show_testing_options=True, num_users=10)
        form.trigger_customer_invoice()

        self.set_user_count.assert_called_with('test_domain', 10, self.start_date, self.end_date,
            overwrite=mock.ANY)

    def test_testing_options_create_user_totals_for_multiple_domains(self):
        self.domains.extend(['domain1', 'domain2'])

        form = self.create_form(show_testing_options=True, num_users=10)
        form.trigger_customer_invoice()

        self.set_user_count.assert_any_call('domain1', 10, self.start_date, self.end_date,
            overwrite=mock.ANY)
        self.set_user_count.assert_any_call('domain2', 10, self.start_date, self.end_date,
            overwrite=mock.ANY)

    def test_will_not_overwrite_existing_user_totals(self):
        self.domains.append('test_domain')

        form = self.create_form(show_testing_options=True, num_users=10)
        form.trigger_customer_invoice()

        self.set_user_count.assert_called_with('test_domain', 10, self.start_date, self.end_date,
            overwrite=False)

    def test_with_overwrite_flag_will_overwrite_user_totals(self):
        self.domains.append('test_domain')

        form = self.create_form(show_testing_options=True, num_users=10, overwrite_user_counts=True)
        form.trigger_customer_invoice()

        self.set_user_count.assert_called_with('test_domain', 10, self.start_date, self.end_date,
            overwrite=True)

    def test_zero_num_users_is_respected(self):
        self.domains.append('test_domain')

        form = self.create_form(show_testing_options=True, num_users=0, overwrite_user_counts=True)
        form.trigger_customer_invoice()

        self.set_user_count.assert_called_with('test_domain', 0, self.start_date, self.end_date,
            overwrite=mock.ANY)
