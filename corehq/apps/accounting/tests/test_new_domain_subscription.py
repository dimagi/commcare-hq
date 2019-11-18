import datetime

from corehq.apps.accounting.exceptions import NewSubscriptionError
from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    EntryPoint,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustmentMethod,
    SubscriptionType,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.domain.models import Domain


class TestNewDomainSubscription(BaseAccountingTest):

    def setUp(self):
        super(TestNewDomainSubscription, self).setUp()
        self.domain = Domain(
            name="test-domain-sub",
            is_active=True,
        )
        self.domain.save()

        self.domain2 = Domain(
            name="test-domain-sub2",
            is_active=True,
        )
        self.domain2.save()

        self.admin_user_name = generator.create_arbitrary_web_user_name()

        self.account = BillingAccount.get_or_create_account_by_domain(
            self.domain.name, created_by=self.admin_user_name)[0]
        self.account2 = BillingAccount.get_or_create_account_by_domain(
            self.domain2.name, created_by=self.admin_user_name)[0]
        self.standard_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.STANDARD)
        self.advanced_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)

    def tearDown(self):
        self.domain.delete()
        self.domain2.delete()
        super(TestNewDomainSubscription, self).tearDown()

    def test_new_susbscription_in_future(self):
        """
        Test covers issue that came up with commcare-hq/PR#3725.
        """
        today = datetime.date.today()
        in_30_days = today + datetime.timedelta(days=30)
        week_after_30 = in_30_days + datetime.timedelta(days=7)
        next_year = week_after_30 + datetime.timedelta(days=400)

        # mimic domain signing up for trial
        trial_subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            date_end=in_30_days,
            adjustment_method=SubscriptionAdjustmentMethod.TRIAL,
            is_trial=True,
        )
        trial_subscription.is_active = True
        trial_subscription.save()

        subscription = Subscription.new_domain_subscription(
            self.account2, self.domain.name, self.standard_plan,
            web_user=self.admin_user_name,
            date_start=week_after_30, date_end=next_year,
        )

        final_sub = Subscription.visible_objects.get(pk=subscription.id)

        self.assertEqual(final_sub.date_start, week_after_30)
        self.assertEqual(final_sub.date_end, next_year)

    def test_conflicting_dates(self):
        """
        Tests creating a subscription with conflicting dates with an existing
        subscription
        """
        today = datetime.date.today()
        one_week = today + datetime.timedelta(days=7)
        one_month = today + datetime.timedelta(days=30)
        Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            date_start=one_week,
            date_end=one_month,
        )

        # conflicting subscription with no date end.
        self.assertRaises(NewSubscriptionError, lambda: Subscription.new_domain_subscription(
            self.account, self.domain.name, self.standard_plan,
        ))

        # conflicting subscription with overlapping end date
        self.assertRaises(NewSubscriptionError, lambda: Subscription.new_domain_subscription(
            self.account, self.domain.name, self.standard_plan,
            date_end=one_week + datetime.timedelta(days=1)
        ))

        # conflicting subscription with overlapping start date
        self.assertRaises(NewSubscriptionError, lambda: Subscription.new_domain_subscription(
            self.account, self.domain.name, self.standard_plan,
            date_start=one_month - datetime.timedelta(days=1)
        ))

        # subscription without overlapping dates before
        # bound future subscription
        sub_before = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.standard_plan,
            date_end=one_week,
        )

        # subscription without overlapping dates after
        # bound future subscription
        sub_after = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.standard_plan,
            date_start=one_month,
        )

    def test_update_billing_account_entry_point_self_serve(self):
        self_serve_subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            web_user=self.admin_user_name, service_type=SubscriptionType.PRODUCT
        )
        self.assertEqual(self_serve_subscription.account.entry_point, EntryPoint.SELF_STARTED)

    def test_update_billing_account_entry_point_contracted(self):
        contracted_subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            web_user=self.admin_user_name, service_type=SubscriptionType.IMPLEMENTATION
        )

        self.assertNotEqual(contracted_subscription.account.entry_point, EntryPoint.SELF_STARTED)

    def test_dont_update_billing_account_if_set(self):
        self.account.entry_point = EntryPoint.CONTRACTED
        self.account.save()

        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            web_user=self.admin_user_name, service_type=SubscriptionType.IMPLEMENTATION
        )

        self.assertEqual(subscription.account.entry_point, EntryPoint.CONTRACTED)

    def test_exceeding_max_domains_prevents_new_domains(self):
        self.advanced_plan.plan.max_domains = 1
        Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan
        )
        self.assertRaises(NewSubscriptionError, lambda: Subscription.new_domain_subscription(
            self.account, self.domain2.name, self.advanced_plan
        ))

    def test_customer_plan_not_added_to_regular_account(self):
        self.advanced_plan.plan.is_customer_software_plan = True
        self.assertRaises(NewSubscriptionError, lambda: Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan
        ))

    def test_regular_plan_not_added_to_customer_account(self):
        self.account.is_customer_billing_account = True
        self.assertRaises(NewSubscriptionError, lambda: Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan
        ))
