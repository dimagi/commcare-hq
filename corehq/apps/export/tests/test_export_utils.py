from datetime import date, timedelta

from django.test import TestCase

from corehq.apps.accounting.models import SoftwarePlanEdition, Subscription, DefaultProductPlan, BillingAccount, \
    SubscriptionAdjustment
from corehq.apps.export.utils import get_default_export_settings_if_available
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.tests import generator


class TestExportUtils(TestCase, DomainSubscriptionMixin):

    def setUp(self):
        super(TestExportUtils, self).setUp()
        self.domain = generator.arbitrary_domain()
        self.account, _ = BillingAccount.get_or_create_account_by_domain(
            self.domain.name,
            created_by='webuser@test.com'
        )
        self.account.save()
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name,
            DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.COMMUNITY),
            date_start=date.today() - timedelta(days=3)
        )
        subscription.is_active = True
        subscription.save()

    def tearDown(self):
        self.domain.delete()
        SubscriptionAdjustment.objects.all().delete()
        Subscription.visible_and_suppressed_objects.all().delete()
        self.account.delete()
        super(TestExportUtils, self).tearDown()

    def update_subscription(self, plan):
        current_subscription = Subscription.get_active_subscription_by_domain(self.domain)
        if current_subscription.plan_version.plan.edition != plan:
            current_subscription.change_plan(DefaultProductPlan.get_default_plan_version(plan))

    def test_default_export_settings_community_domain_returns_none(self):
        """
        Verify COMMUNITY software plans do not have access to default export settings
        """
        self.update_subscription(SoftwarePlanEdition.COMMUNITY)
        settings = get_default_export_settings_if_available(self.domain)
        self.assertIsNone(settings)

    def test_default_export_settings_standard_domain_returns_none(self):
        """
        Verify STANDARD software plans do not have access to default export settings
        """
        self.update_subscription(SoftwarePlanEdition.STANDARD)
        settings = get_default_export_settings_if_available(self.domain)
        self.assertIsNone(settings)

    def test_default_export_settings_pro_domain_returns_none(self):
        """
        Verify PRO software plans do not have access to default export settings
        """
        self.update_subscription(SoftwarePlanEdition.PRO)
        settings = get_default_export_settings_if_available(self.domain)
        self.assertIsNone(settings)

    def test_default_export_settings_advanced_domain_returns_none(self):
        """
        Verify ADVANCED software plans do not have access to default export settings
        """
        self.update_subscription(SoftwarePlanEdition.ADVANCED)
        settings = get_default_export_settings_if_available(self.domain)
        self.assertIsNone(settings)

    def test_default_export_settings_reseller_domain_returns_none(self):
        """
        Verify RESELLER software plans do not have access to default export settings
        """
        self.update_subscription(SoftwarePlanEdition.RESELLER)
        settings = get_default_export_settings_if_available(self.domain)
        self.assertIsNone(settings)

    def test_default_export_settings_managed_hosting_domain_returns_none(self):
        """
        Verify MANAGED_HOSTING software plans do not have access to default export settings
        """
        self.update_subscription(SoftwarePlanEdition.MANAGED_HOSTING)
        settings = get_default_export_settings_if_available(self.domain)
        self.assertIsNone(settings)

    def test_default_export_settings_enterprise_domain_returns_not_none(self):
        """
        Verify software plan editions that have access to default export settings
        are able to create a DefaultExportSettings instance
        """
        self.update_subscription(SoftwarePlanEdition.ENTERPRISE)
        settings = get_default_export_settings_if_available(self.domain)
        self.assertIsNotNone(settings)
