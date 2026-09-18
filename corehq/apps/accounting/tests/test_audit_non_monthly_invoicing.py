import datetime

from django.test import TestCase

from corehq.apps.accounting.management.commands.audit_non_monthly_invoicing import (
    get_customer_invoice_stats,
    get_multi_month_invoices,
    get_non_monthly_accounts,
    get_subscription_stats,
    group_multi_month_customer_invoices,
)
from corehq.apps.accounting.models import (
    CustomerInvoice,
    InvoicingPlan,
)
from corehq.apps.accounting.tests import generator


class TestGetNonMonthlyAccounts(TestCase):

    @classmethod
    def setUpTestData(cls):
        generator.init_default_currency()
        cls.monthly = cls._account(InvoicingPlan.MONTHLY)
        cls.quarterly = cls._account(InvoicingPlan.QUARTERLY)
        cls.yearly = cls._account(InvoicingPlan.YEARLY)
        cls.inactive_yearly = cls._account(InvoicingPlan.YEARLY, is_active=False)

    @classmethod
    def _account(cls, invoicing_plan, is_active=True):
        account = generator.billing_account(
            generator.create_arbitrary_web_user_name(is_dimagi=True),
            generator.create_arbitrary_web_user_name(),
        )
        account.invoicing_plan = invoicing_plan
        account.is_active = is_active
        account.save()
        return account

    def test_excludes_monthly_accounts(self):
        assert self.monthly not in set(get_non_monthly_accounts())

    def test_includes_quarterly_and_yearly_accounts(self):
        assert set(get_non_monthly_accounts()) == {
            self.quarterly, self.yearly, self.inactive_yearly
        }


class TestGetMultiMonthInvoices(TestCase):
    """
    The billing period of a customer invoice is the only durable record of
    quarterly or yearly invoicing, since ``invoicing_plan`` has no history.
    """

    @classmethod
    def setUpTestData(cls):
        generator.init_default_currency()
        cls.account = generator.billing_account(
            generator.create_arbitrary_web_user_name(is_dimagi=True),
            generator.create_arbitrary_web_user_name(),
        )
        cls.account.is_customer_billing_account = True
        cls.account.invoicing_plan = InvoicingPlan.QUARTERLY
        cls.account.save()
        cls.invoices = {
            label: CustomerInvoice.objects.create(
                account=cls.account,
                date_start=datetime.date(*start),
                date_end=datetime.date(*end),
            )
            for label, start, end in [
                ('monthly', (2020, 1, 1), (2020, 1, 31)),
                ('monthly_february', (2020, 2, 1), (2020, 2, 29)),
                ('quarterly', (2020, 4, 1), (2020, 6, 30)),
                ('yearly', (2021, 1, 1), (2021, 12, 31)),
                ('crosses_year_end', (2019, 10, 1), (2020, 3, 31)),
                ('straddles_two_months', (2022, 1, 15), (2022, 2, 14)),
            ]
        }

    def _months_spanned(self, label):
        invoice = CustomerInvoice.objects.filter(id=self.invoices[label].id)
        return get_multi_month_invoices(invoice).values_list(
            'months_spanned', flat=True
        ).first()

    def test_single_month_invoices_are_excluded(self):
        flagged = get_multi_month_invoices(CustomerInvoice.objects.all())
        assert self.invoices['monthly'] not in set(flagged)
        assert self.invoices['monthly_february'] not in set(flagged)

    def test_multi_month_invoices_are_included(self):
        assert set(get_multi_month_invoices(CustomerInvoice.objects.all())) == {
            self.invoices['quarterly'],
            self.invoices['yearly'],
            self.invoices['crosses_year_end'],
            self.invoices['straddles_two_months'],
        }

    def test_months_spanned_counts_calendar_months(self):
        assert self._months_spanned('quarterly') == 3
        assert self._months_spanned('yearly') == 12

    def test_months_spanned_across_a_year_boundary(self):
        assert self._months_spanned('crosses_year_end') == 6

    def test_partial_months_are_counted_as_the_months_they_touch(self):
        # Monthly invoices always run from the first to the last day of a
        # month, so a period like this is not a monthly invoice either.
        assert self._months_spanned('straddles_two_months') == 2

    def test_invoices_hidden_to_ops_are_included(self):
        hidden = CustomerInvoice.objects.create(
            account=self.account,
            date_start=datetime.date(2023, 1, 1),
            date_end=datetime.date(2023, 3, 31),
            is_hidden_to_ops=True,
        )
        grouped = group_multi_month_customer_invoices()
        assert hidden in set(grouped[self.account.id])

    def test_grouped_by_account(self):
        grouped = group_multi_month_customer_invoices()
        assert set(grouped) == {self.account.id}
        assert len(grouped[self.account.id]) == 4

    def test_customer_invoice_stats(self):
        stats = get_customer_invoice_stats([self.account.id])
        assert stats[self.account.id]['invoices'] == 6
        assert stats[self.account.id]['latest_end'] == datetime.date(2022, 2, 14)


class TestGetSubscriptionStats(TestCase):

    @classmethod
    def setUpTestData(cls):
        generator.init_default_currency()
        cls.account = generator.billing_account(
            generator.create_arbitrary_web_user_name(is_dimagi=True),
            generator.create_arbitrary_web_user_name(),
        )
        cls.domain = generator.arbitrary_domain()
        cls.addClassCleanup(cls.domain.delete)
        generator.generate_domain_subscription(
            cls.account, cls.domain,
            date_start=datetime.date(2019, 1, 1),
            date_end=datetime.date(2019, 12, 31),
        )
        generator.generate_domain_subscription(
            cls.account, cls.domain,
            date_start=datetime.date(2020, 1, 1),
            date_end=datetime.date(2020, 6, 30),
            is_hidden_to_ops=True,
        )
        generator.generate_domain_subscription(
            cls.account, cls.domain,
            date_start=datetime.date(2020, 7, 1),
            date_end=None,
            is_active=True,
        )

    def test_counts_include_subscriptions_hidden_to_ops(self):
        stats = get_subscription_stats([self.account.id])[self.account.id]
        assert stats['subscriptions'] == 3
        assert stats['active'] == 1
        assert stats['open_ended'] == 1
        assert stats['latest_end'] == datetime.date(2020, 6, 30)

    def test_accounts_without_subscriptions_are_absent(self):
        assert get_subscription_stats([]) == {}
