import datetime

from django_prbac.models import Role

from corehq.apps.accounting.models import (
    SoftwarePlan,
    SoftwarePlanEdition,
    SoftwarePlanVisibility,
    SoftwarePlanVersion,
    SoftwareProductRate,
    Subscription,
    SubscriptionType,
)
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.utils.software_plans import \
    upgrade_subscriptions_to_latest_plan_version


class TestUpgradeSoftwarePlanToLatestVersion(BaseAccountingTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain1, subscriber1 = generator.arbitrary_domain_and_subscriber()
        cls.domain2, subscriber2 = generator.arbitrary_domain_and_subscriber()
        cls.admin_web_user = generator.create_arbitrary_web_user_name()

        account = generator.billing_account(cls.admin_web_user, cls.admin_web_user)
        account.is_customer_billing_account = True
        account.save()

        enterprise_plan = SoftwarePlan.objects.create(
            name="Helping Earth INGO Enterprise Plan",
            description="Enterprise plan for Helping Earth",
            edition=SoftwarePlanEdition.ENTERPRISE,
            visibility=SoftwarePlanVisibility.INTERNAL,
            is_customer_software_plan=True,
        )

        first_product_rate = SoftwareProductRate.objects.create(
            monthly_fee=3000,
            name="HQ Enterprise"
        )
        cls.first_version = SoftwarePlanVersion.objects.create(
            plan=enterprise_plan,
            role=Role.objects.first(),
            product_rate=first_product_rate
        )
        cls.first_version.save()

        today = datetime.date.today()
        two_months_ago = today - datetime.timedelta(days=60)
        next_month = today + datetime.timedelta(days=30)

        subscription1 = Subscription(
            account=account,
            plan_version=cls.first_version,
            subscriber=subscriber1,
            date_start=two_months_ago,
            date_end=None,
            service_type=SubscriptionType.IMPLEMENTATION,
        )
        subscription1.is_active = True
        subscription1.save()

        subscription2 = Subscription(
            account=account,
            plan_version=cls.first_version,
            subscriber=subscriber2,
            date_start=two_months_ago,
            date_end=next_month,
            service_type=SubscriptionType.IMPLEMENTATION,
        )
        subscription2.is_active = True
        subscription2.save()

        new_product_rate = SoftwareProductRate.objects.create(
            monthly_fee=5000,
            name="HQ Enterprise"
        )
        cls.newest_version = SoftwarePlanVersion.objects.create(
            plan=enterprise_plan,
            role=Role.objects.first(),
            product_rate=new_product_rate
        )
        cls.newest_version.save()

    def test_that_upgrade_occurs(self):
        self.assertEqual(
            Subscription.get_subscribed_plan_by_domain(self.domain1),
            self.first_version
        )
        self.assertEqual(
            Subscription.get_subscribed_plan_by_domain(self.domain2),
            self.first_version
        )
        upgrade_subscriptions_to_latest_plan_version(
            self.first_version,
            self.admin_web_user,
            datetime.date.today(),
            upgrade_note="test upgrading to latest version"
        )
        self.assertEqual(
            Subscription.get_subscribed_plan_by_domain(self.domain1),
            self.newest_version
        )
        self.assertEqual(
            Subscription.get_subscribed_plan_by_domain(self.domain2),
            self.newest_version
        )
