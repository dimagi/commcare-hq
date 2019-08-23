import datetime

from corehq.apps.accounting.models import (
    Subscription,
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.domain.models import Domain


class TestRenewSubscriptions(BaseAccountingTest):

    def setUp(self):
        super(TestRenewSubscriptions, self).setUp()
        self.domain = Domain(
            name="test-domain-sub",
            is_active=True,
        )
        self.domain.save()

        self.admin_username = generator.create_arbitrary_web_user_name()

        self.account = BillingAccount.get_or_create_account_by_domain(
            self.domain.name, created_by=self.admin_username)[0]

        self.standard_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.STANDARD)

        today = datetime.date.today()
        yesterday = today + datetime.timedelta(days=-1)
        tomorrow = today + datetime.timedelta(days=1)

        self.subscription = Subscription.new_domain_subscription(
            self.account,
            self.domain.name,
            self.standard_plan,
            web_user=self.admin_username,
            date_start=yesterday,
            date_end=tomorrow,
        )

        self.subscription.save()

    def tearDown(self):
        self.domain.delete()
        super(TestRenewSubscriptions, self).tearDown()

    def test_simple_renewal(self):
        self.renewed_subscription = self.subscription.renew_subscription()

        self.assertEqual(self.renewed_subscription.date_end, None)
        self.assertEqual(self.renewed_subscription.date_start, self.subscription.date_end)
        self.assertEqual(self.renewed_subscription.plan_version, self.subscription.plan_version)

    def test_change_plan_on_renewal(self):
        new_edition = SoftwarePlanEdition.ADVANCED
        new_plan = DefaultProductPlan.get_default_plan_version(new_edition)

        self.renewed_subscription = self.subscription.renew_subscription(
            new_version=new_plan
        )

        self.assertEqual(self.renewed_subscription.plan_version, new_plan)

    def test_next_subscription_filter(self):
        """
        If subscription.next_subscription is None then subscription.is_renewed should be False
        """
        self.renewed_subscription = self.subscription.renew_subscription()
        self.renewed_subscription.date_end = self.renewed_subscription.date_start  # Not a valid subscription
        self.renewed_subscription.save()

        self.assertIsNone(self.subscription.next_subscription)
        self.assertFalse(self.subscription.is_renewed)

    def test_next_subscription_filter_no_end_date(self):
        next_subscription = Subscription(
            account=self.subscription.account,
            plan_version=self.subscription.plan_version,
            subscriber=self.subscription.subscriber,
            date_start=self.subscription.date_end,
            date_end=None,
        )
        next_subscription.save()
        self.assertEqual(next_subscription, self.subscription.next_subscription)
