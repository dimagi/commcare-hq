import datetime
from corehq.apps.domain.models import Domain
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting import generator
from corehq.apps.accounting.models import (
    Subscription,
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition
)


class TestRenewSubscriptions(BaseAccountingTest):

    def setUp(self):
        super(TestRenewSubscriptions, self).setUp()
        self.domain = Domain(
            name="test-domain-sub",
            is_active=True,
        )
        self.domain.save()

        self.admin_user = generator.arbitrary_web_user()
        self.admin_user.add_domain_membership(self.domain.name, is_admin=True)
        self.admin_user.save()

        self.account = BillingAccount.get_or_create_account_by_domain(
            self.domain.name, created_by=self.admin_user.username)[0]

        self.standard_plan = DefaultProductPlan.get_default_plan_by_domain(
            self.domain.name, edition=SoftwarePlanEdition.STANDARD)

        today = datetime.date.today()
        yesterday = today + datetime.timedelta(days=-1)
        tomorrow = today + datetime.timedelta(days=1)

        self.subscription = Subscription.new_domain_subscription(
            self.account,
            self.domain.name,
            self.standard_plan,
            web_user=self.admin_user.username,
            date_start=yesterday,
            date_end=tomorrow,
        )

        self.subscription.save()

    def test_simple_renewal(self):
        today = datetime.date.today()

        renewed_subscription = self.subscription.renew_subscription()

        self.assertEqual(renewed_subscription.date_end, None)
        self.assertEqual(renewed_subscription.date_start, self.subscription.date_end)
        self.assertEqual(renewed_subscription.plan_version, self.subscription.plan_version)

    def test_change_plan_on_renewal(self):
        today = datetime.date.today()
        new_edition = SoftwarePlanEdition.ADVANCED
        new_plan = DefaultProductPlan.get_default_plan_by_domain(self.domain.name, new_edition)

        renewed_subscription = self.subscription.renew_subscription(
            new_version=new_plan
        )

        self.assertEqual(renewed_subscription.plan_version, new_plan)
