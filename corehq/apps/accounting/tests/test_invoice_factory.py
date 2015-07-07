import datetime
from corehq.apps.accounting import generator
from corehq.apps.accounting.invoicing import DomainInvoiceFactory
from corehq.apps.accounting.models import (
    DefaultProductPlan,
    BillingAccount,
    Subscription,
    SubscriptionAdjustment,
)
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.utils import get_previous_month_date_range


class TestDomainInvoiceFactory(BaseAccountingTest):

    def setUp(self):
        super(TestDomainInvoiceFactory, self).setUp()
        self.invoice_start, self.invoice_end = get_previous_month_date_range()

        self.domain = generator.arbitrary_domain()
        self.account = BillingAccount.get_or_create_account_by_domain(
            domain=self.domain.name, created_by="TEST"
        )[0]
        self.community = DefaultProductPlan.get_default_plan_by_domain(
            self.domain).plan.get_version()
        generator.arbitrary_commcare_users_for_domain(
            self.domain.name, self.community.user_limit + 1
        )

        self.invoice_factory = DomainInvoiceFactory(
            self.invoice_start, self.invoice_end, self.domain
        )

    def _clean_subs(self):
        SubscriptionAdjustment.objects.all().delete()
        Subscription.objects.all().delete()

    def test_feature_charges(self):
        domain_under_limits = generator.arbitrary_domain()
        self.assertTrue(self.community.feature_charges_exist_for_domain(self.domain))
        self.assertFalse(self.community.feature_charges_exist_for_domain(domain_under_limits))

    def test_incomplete_starting_coverage(self):
        some_plan = generator.arbitrary_subscribable_plan()
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain, some_plan,
            date_start=self.invoice_start + datetime.timedelta(days=3)
        )
        subscriptions = self.invoice_factory.get_subscriptions()
        community_ranges = self.invoice_factory.get_community_ranges(subscriptions)
        self.assertEqual(len(community_ranges), 1)
        self.assertEqual(community_ranges[0][0], self.invoice_start)
        self.assertEqual(community_ranges[0][1], subscription.date_start)
        self._clean_subs()

    def test_incomplete_ending_coverage(self):
        some_plan = generator.arbitrary_subscribable_plan()
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain, some_plan,
            date_start=self.invoice_start,
            date_end=self.invoice_end - datetime.timedelta(days=3)
        )
        subscriptions = self.invoice_factory.get_subscriptions()
        community_ranges = self.invoice_factory.get_community_ranges(subscriptions)
        self.assertEqual(len(community_ranges), 1)
        self.assertEqual(community_ranges[0][0], subscription.date_end)
        self.assertEqual(community_ranges[0][1],
                         self.invoice_end + datetime.timedelta(days=1))
        self._clean_subs()

    def test_patchy_coverage(self):
        some_plan = generator.arbitrary_subscribable_plan()
        middle_date = self.invoice_end - datetime.timedelta(days=15)
        Subscription.new_domain_subscription(
            self.account, self.domain, some_plan,
            date_start=self.invoice_start + datetime.timedelta(days=1),
            date_end=middle_date
        )
        next_start = middle_date + datetime.timedelta(days=2)
        next_end = next_start + datetime.timedelta(days=2)
        Subscription.new_domain_subscription(
            self.account, self.domain, some_plan,
            date_start=next_start,
            date_end=next_end,
        )
        final_start = next_end + datetime.timedelta(days=2)
        Subscription.new_domain_subscription(
            self.account, self.domain, some_plan,
            date_start=final_start,
            date_end=self.invoice_end - datetime.timedelta(days=1),
        )
        subscriptions = self.invoice_factory.get_subscriptions()
        self.assertEqual(len(subscriptions), 3)
        community_ranges = self.invoice_factory.get_community_ranges(subscriptions)
        self.assertEqual(len(community_ranges), 4)
        self._clean_subs()

    def test_full_coverage(self):
        some_plan = generator.arbitrary_subscribable_plan()
        Subscription.new_domain_subscription(
            self.account, self.domain, some_plan,
            date_start=self.invoice_start,
            date_end=self.invoice_end + datetime.timedelta(days=1),
        )
        subscriptions = self.invoice_factory.get_subscriptions()
        community_ranges = self.invoice_factory.get_community_ranges(subscriptions)
        self.assertEqual(len(community_ranges), 0)
        self._clean_subs()

    def test_no_coverage(self):
        subscriptions = self.invoice_factory.get_subscriptions()
        self.assertEqual(len(subscriptions), 0)
        community_ranges = self.invoice_factory.get_community_ranges(subscriptions)
        self.assertEqual(len(community_ranges), 1)
