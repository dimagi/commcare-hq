import datetime
from corehq import Domain
from corehq.apps.accounting import generator
from corehq.apps.accounting.models import (
    Subscription, BillingAccount, DefaultProductPlan, SoftwarePlanEdition,
    SubscriptionAdjustmentMethod)
from corehq.apps.accounting.tests import BaseAccountingTest


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

        self.admin_user = generator.arbitrary_web_user()
        self.admin_user.add_domain_membership(self.domain.name, is_admin=True)
        self.admin_user.save()

        self.account = BillingAccount.get_or_create_account_by_domain(
            self.domain.name, created_by=self.admin_user.username)[0]
        self.account2 = BillingAccount.get_or_create_account_by_domain(
            self.domain2.name, created_by=self.admin_user.username)[0]
        self.standard_plan = DefaultProductPlan.get_default_plan_by_domain(
            self.domain.name, edition=SoftwarePlanEdition.STANDARD)
        self.advanced_plan = DefaultProductPlan.get_default_plan_by_domain(
            self.domain.name, edition=SoftwarePlanEdition.ADVANCED)

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
            web_user=self.admin_user.username,
            date_start=week_after_30, date_end=next_year,
        )

        final_sub = Subscription.objects.get(pk=subscription.id)

        self.assertEqual(final_sub.date_start, week_after_30)
        self.assertEqual(final_sub.date_end, next_year)

