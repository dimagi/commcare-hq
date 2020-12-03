# 11 Tests, 0.180s

import datetime
from unittest import mock
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase

from corehq.apps.accounting.forms import TriggerInvoiceForm
from corehq.apps.accounting.exceptions import InvoiceError
from corehq.apps.accounting.models import DomainUserHistory, Invoice


def create_form(domain='test_domain', month=1, year=2020, num_users=0, show_testing_options=False):
    data = {
        'month': month,
        'year': year,
        'domain': domain,
        'num_users': num_users
    }
    return TriggerInvoiceForm(data, show_testing_options=show_testing_options)


class TestTriggerInvoiceFormValidity(SimpleTestCase):
    def test_has_all_details_is_valid_form(self):
        form = create_form()
        self.assertTrue(form.is_valid())

    def test_missing_month_is_invalid(self):
        form = create_form(month=None)
        self.assertFalse(form.is_valid())

    def test_missing_year_is_invalid(self):
        form = create_form(year=None)
        self.assertFalse(form.is_valid())

    def test_missing_domain_is_invalid(self):
        form = create_form(domain='')
        self.assertFalse(form.is_valid())

    def test_current_periods_are_not_valid(self):
        current_date = datetime.date(2020, 1, 10)
        form = create_form(month=1, year=2020)
        with mock.patch('corehq.apps.accounting.forms.datetime') as mock_datetime:
            mock_datetime.date.today.return_value = current_date
            self.assertFalse(form.is_valid())

    def test_if_testing_options_are_enabled_then_num_users_is_displayed(self):
        form = create_form(show_testing_options=True)
        self.assertIn('num_users', form.fields)

    def test_if_testing_options_are_disabled_then_num_users_is_hidden(self):
        form = create_form(show_testing_options=False)
        self.assertNotIn('num_users', form.fields)


# cannot use SimpleTestCase due to transaction.atomic -- and that behavior should be tested.
# Ultimately it likely means form and database behavior should be separated,
# so that form can use SimpleTestCase, and database can use TestCase
class TestMockedInvoiceForm(TestCase):
    def setUp(self):
        self.month = 1
        self.year = 2020
        self.start_date = datetime.date(self.year, self.month, 1)
        self.end_date = datetime.date(self.year, self.month, 31)

        self.create_mocks()

    def create_mocks(self):
        get_invoices_patcher = patch.object(Invoice,
                'get_domain_invoices_between_dates', return_value=[])
        self.get_existing_invoices = get_invoices_patcher.start()
        self.addCleanup(get_invoices_patcher.stop)

        invoice_factory_patcher = patch('corehq.apps.accounting.forms.DomainInvoiceFactory')
        invoice_factory_patcher.start()
        self.addCleanup(invoice_factory_patcher.stop)

        # Reverse mocked out because it takes ~1 second to generate the lookup table
        reverse_patcher = mock.patch('corehq.apps.accounting.forms.reverse',
            return_value='some.url')
        reverse_patcher.start()
        self.addCleanup(reverse_patcher.stop)

    def create_form(self, **kwargs):
        kwargs['month'] = self.month
        kwargs['year'] = self.year

        return create_form(**kwargs)

    def test_when_invoice_exists_throws_exception(self):
        form = create_form()

        existing_invoice = mock.MagicMock(id=1, invoice_number=57)
        self.get_existing_invoices.return_value = [existing_invoice]

        with self.assertRaises(InvoiceError) as context:
            form.trigger_invoice()

        self.assertIn('Invoices exist that were already generated'
            ' with this same criteria.', str(context.exception))

    @patch.object(DomainUserHistory, 'set_domain_user_count_during_period')
    def test_num_users_generates_user_counts(self, set_domain_user_count_during_period):
        form = create_form(show_testing_options=True, domain='my_domain', num_users=90)
        form.trigger_invoice()

        set_domain_user_count_during_period.assert_called_with(
            'my_domain', 90, self.start_date, self.end_date, overwrite=mock.ANY)

    @patch.object(DomainUserHistory, 'set_domain_user_count_during_period')
    def test_zero_num_users_is_respected(self, set_domain_user_count_during_period):
        form = create_form(show_testing_options=True, domain='my_domain', num_users=0)
        form.trigger_invoice()

        set_domain_user_count_during_period.assert_called_with(
            'my_domain', 0, self.start_date, self.end_date, overwrite=mock.ANY)

    @patch.object(DomainUserHistory, 'set_domain_user_count_during_period')
    def test_overwrites_existing_counts(self, set_domain_user_count_during_period):
        form = create_form(show_testing_options=True, domain='my_domain', num_users=5)
        form.trigger_invoice()

        set_domain_user_count_during_period.assert_called_with(
            'my_domain', 5, self.start_date, self.end_date, overwrite=True)
