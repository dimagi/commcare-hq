# 11 Tests, 11.839s

import datetime
from unittest import mock
from django.test import TestCase, SimpleTestCase

from corehq.apps.domain.models import Domain
from corehq.apps.accounting.models import BillingAccount, Invoice, Subscription, DomainUserHistory
from corehq.apps.accounting.exceptions import InvoiceError
from corehq.apps.accounting.forms import TriggerInvoiceForm
from corehq.apps.accounting.tests import generator


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


class TestTriggerInvoiceForm(TestCase):
    def setUp(self):
        self.month = 1
        self.year = 2020
        self.start_date = datetime.date(self.year, self.month, 1)
        self.end_date = datetime.date(self.year, self.month, 31)

        self.domain_obj = None

    def tearDown(self):
        if self.domain_obj:
            self.domain_obj.delete()

    def create_form(self, **kwargs):
        kwargs['month'] = self.month
        kwargs['year'] = self.year

        return create_form(**kwargs)

    def create_billing_account(self):
        return BillingAccount.create_account_for_domain('test_domain', created_by='TEST')

    def create_invoice(self):
        subscription, _ = self.create_subscription()
        return Invoice.objects.create(subscription=subscription, date_start=self.start_date,
                date_end=self.end_date)

    def create_subscription(self, domain='test_domain'):
        self.domain_obj = Domain(name=domain, is_active=True)
        self.domain_obj.save()

        billing_account_obj = self.create_billing_account()

        plan = generator.subscribable_plan_version()
        subscription_obj = Subscription.new_domain_subscription(billing_account_obj, domain,
                plan, date_start=self.start_date)

        return (subscription_obj, self.domain_obj)

    def test_when_invoice_exists_throws_exception(self):
        self.create_invoice()
        form = create_form()
        with self.assertRaises(InvoiceError) as context:
            form.trigger_invoice()

        self.assertIn('Invoices exist that were already generated'
        ' with this same criteria.', str(context.exception))

    def test_num_users_generates_user_counts(self):
        _, domain_obj = self.create_subscription()
        form = self.create_form(show_testing_options=True, num_users=90)

        form.trigger_invoice()

        user_count = DomainUserHistory.objects.get(domain=domain_obj)
        self.assertEqual(user_count.num_users, 90)

    def test_zero_num_users_is_respected(self):
        _, domain_obj = self.create_subscription()
        form = self.create_form(show_testing_options=True, num_users=0)

        form.trigger_invoice()

        user_count = DomainUserHistory.objects.get(domain=domain_obj)
        self.assertEqual(user_count.num_users, 0)

    def test_num_users_overwrites_existing_user_counts(self):
        _, domain_obj = self.create_subscription()
        DomainUserHistory.objects.create(domain=domain_obj, record_date=self.end_date, num_users=40)
        form = self.create_form(show_testing_options=True, num_users=90)

        form.trigger_invoice()

        user_count = DomainUserHistory.objects.get(domain=domain_obj)
        self.assertEqual(user_count.num_users, 90)
