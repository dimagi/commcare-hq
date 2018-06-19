from __future__ import absolute_import
from __future__ import unicode_literals
import datetime

from corehq.apps.accounting.invoicing import DomainInvoiceFactory, CustomerAccountInvoiceFactory
from corehq.apps.accounting.models import (
    DefaultProductPlan,
    BillingAccount,
    Subscription,
    SubscriptionAdjustment,
    SoftwarePlanEdition
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.util.dates import get_previous_month_date_range


class TestDomainInvoiceFactory(BaseAccountingTest):

    @classmethod
    def setUpClass(cls):
        super(TestDomainInvoiceFactory, cls).setUpClass()
        generator.bootstrap_test_software_plan_versions()

    def setUp(self):
        super(TestDomainInvoiceFactory, self).setUp()
        self.invoice_start, self.invoice_end = get_previous_month_date_range()

        self.domain = generator.arbitrary_domain()
        self.account = BillingAccount.get_or_create_account_by_domain(
            domain=self.domain.name, created_by="TEST"
        )[0]
        self.community = DefaultProductPlan.get_default_plan_version()
        generator.arbitrary_commcare_users_for_domain(
            self.domain.name, self.community.user_limit + 1
        )

        self.invoice_factory = DomainInvoiceFactory(
            self.invoice_start, self.invoice_end, self.domain
        )

    def tearDown(self):
        self.domain.delete()
        super(TestDomainInvoiceFactory, self).tearDown()

    def test_feature_charges(self):
        domain_under_limits = generator.arbitrary_domain()
        self.assertTrue(self.community.feature_charges_exist_for_domain(self.domain))
        self.assertFalse(self.community.feature_charges_exist_for_domain(domain_under_limits))
        domain_under_limits.delete()

    def test_incomplete_starting_coverage(self):
        some_plan = generator.subscribable_plan_version()
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, some_plan,
            date_start=self.invoice_start + datetime.timedelta(days=3)
        )
        subscriptions = self.invoice_factory._get_subscriptions()
        community_ranges = self.invoice_factory._get_community_ranges(subscriptions)
        self.assertEqual(len(community_ranges), 1)
        self.assertEqual(community_ranges[0][0], self.invoice_start)
        self.assertEqual(community_ranges[0][1], subscription.date_start)

    def test_incomplete_ending_coverage(self):
        some_plan = generator.subscribable_plan_version()
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, some_plan,
            date_start=self.invoice_start,
            date_end=self.invoice_end - datetime.timedelta(days=3)
        )
        subscriptions = self.invoice_factory._get_subscriptions()
        community_ranges = self.invoice_factory._get_community_ranges(subscriptions)
        self.assertEqual(len(community_ranges), 1)
        self.assertEqual(community_ranges[0][0], subscription.date_end)
        self.assertEqual(community_ranges[0][1],
                         self.invoice_end + datetime.timedelta(days=1))

    def test_patchy_coverage(self):
        some_plan = generator.subscribable_plan_version()
        middle_date = self.invoice_end - datetime.timedelta(days=15)
        Subscription.new_domain_subscription(
            self.account, self.domain.name, some_plan,
            date_start=self.invoice_start + datetime.timedelta(days=1),
            date_end=middle_date
        )
        next_start = middle_date + datetime.timedelta(days=2)
        next_end = next_start + datetime.timedelta(days=2)
        Subscription.new_domain_subscription(
            self.account, self.domain.name, some_plan,
            date_start=next_start,
            date_end=next_end,
        )
        final_start = next_end + datetime.timedelta(days=2)
        Subscription.new_domain_subscription(
            self.account, self.domain.name, some_plan,
            date_start=final_start,
            date_end=self.invoice_end - datetime.timedelta(days=1),
        )
        subscriptions = self.invoice_factory._get_subscriptions()
        self.assertEqual(len(subscriptions), 3)
        community_ranges = self.invoice_factory._get_community_ranges(subscriptions)
        self.assertEqual(len(community_ranges), 4)

    def test_full_coverage(self):
        some_plan = generator.subscribable_plan_version()
        Subscription.new_domain_subscription(
            self.account, self.domain.name, some_plan,
            date_start=self.invoice_start,
            date_end=self.invoice_end + datetime.timedelta(days=1),
        )
        subscriptions = self.invoice_factory._get_subscriptions()
        community_ranges = self.invoice_factory._get_community_ranges(subscriptions)
        self.assertEqual(len(community_ranges), 0)

    def test_no_coverage(self):
        subscriptions = self.invoice_factory._get_subscriptions()
        self.assertEqual(len(subscriptions), 0)
        community_ranges = self.invoice_factory._get_community_ranges(subscriptions)
        self.assertEqual(community_ranges, [(self.invoice_start, self.invoice_end + datetime.timedelta(days=1))])


class TestCustomerInvoiceFactory(BaseAccountingTest):

    def setUp(self):
        super(TestCustomerInvoiceFactory, self).setUp()
        self.invoice_start, self.invoice_end = get_previous_month_date_range()

        self.domain1 = generator.arbitrary_domain()
        self.domain2 = generator.arbitrary_domain()
        self.domain3 = generator.arbitrary_domain()
        self.account = BillingAccount.get_or_create_account_by_domain(
            domain=self.domain1.name, created_by="TEST"
        )[0]
        self.account.is_customer_billing_account = True
        self.account.save()
        self.invoice_factory = CustomerAccountInvoiceFactory(self.invoice_start, self.invoice_end, self.account)
        self.advanced_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        self.advanced_plan.plan.is_customer_software_plan = True
        self.pro_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.PRO)
        self.pro_plan.plan.is_customer_software_plan = True
        self.sub1 = Subscription.new_domain_subscription(
            self.account, self.domain1.name, self.advanced_plan, date_start=self.invoice_start
        )
        self.sub2 = Subscription.new_domain_subscription(
            self.account, self.domain2.name, self.advanced_plan, date_start=self.invoice_start
        )
        self.sub3 = Subscription.new_domain_subscription(
            self.account, self.domain3.name, self.pro_plan, date_start=self.invoice_start
        )

    def tearDown(self):
        self.domain1.delete()
        self.domain2.delete()
        self.domain3.delete()
        super(TestCustomerInvoiceFactory, self).tearDown()

    def test_create_invoice_for_subscription(self):
        invoice = self.invoice_factory._generate_invoice(self.sub1, self.invoice_start, self.invoice_end)
        self.assertTrue(invoice.exists_for_domain(self.domain1))
        self.assertEqual(invoice.account, self.account)
        self.assertEqual(invoice.date_start, self.invoice_start)
        self.assertEqual(invoice.date_end, self.invoice_end)
        self.assertEqual(invoice.lineitem_set.count(), 3)
        self.assertEqual(invoice.subscription, self.sub1)

    def test_consolidate_invoices(self):
        invoice1 = self.invoice_factory._generate_invoice(self.sub1, self.invoice_start, self.invoice_end)
        invoice2 = self.invoice_factory._generate_invoice(self.sub2, self.invoice_start, self.invoice_end)
        invoice3 = self.invoice_factory._generate_invoice(self.sub3, self.invoice_start, self.invoice_end)
        invoices = [invoice1, invoice2, invoice3]
        total_balance = 0
        total_line_items = 0
        for invoice in invoices:
            total_balance += invoice.balance
            total_line_items += invoice.lineitem_set.count()

        invoice = self.invoice_factory._consolidate_invoices(invoices)
        self.assertEqual(invoice.account, self.account)
        self.assertEqual(invoice.date_start, self.invoice_start)
        self.assertEqual(invoice.date_end, self.invoice_end)
        self.assertEqual(invoice.lineitem_set.count(), total_line_items)
        self.assertEqual(invoice.balance, total_balance)
