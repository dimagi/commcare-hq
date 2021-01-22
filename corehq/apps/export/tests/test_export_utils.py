from datetime import date, timedelta

from django.test import TestCase

from corehq.apps.accounting.models import SoftwarePlanEdition, Subscription, DefaultProductPlan, BillingAccount, \
    SubscriptionAdjustment
from corehq.apps.domain.models import Domain
from corehq.apps.export.utils import get_or_create_default_export_settings_for_domain
from corehq.util.test_utils import flag_enabled


class TestExportUtils(TestCase):

    def setUp(self):
        super(TestExportUtils, self).setUp()
        self.domain = Domain.get_or_create_with_name('test-export-utils', is_active=True)
        self.account, _ = BillingAccount.get_or_create_account_by_domain(
            self.domain.name,
            created_by='webuser@test.com'
        )
        self.account.save()
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name,
            DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ENTERPRISE),
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

    def test_default_export_settings_no_ff_enabled(self):
        """
        Default export settings are only available if the feature flag is enabled
        NOTE: no decorator to enable DEFAULT_EXPORT_SETTINGS feature flag
        """
        self.update_subscription(SoftwarePlanEdition.ENTERPRISE)
        settings = get_or_create_default_export_settings_for_domain(self.domain)
        self.assertIsNone(settings)

    @flag_enabled('DEFAULT_EXPORT_SETTINGS')
    def test_default_export_settings_community_domain(self):
        """
        Verify COMMUNITY software plans do not have access to default export settings
        """
        self.update_subscription(SoftwarePlanEdition.COMMUNITY)
        settings = get_or_create_default_export_settings_for_domain(self.domain)
        self.assertIsNone(settings)

    @flag_enabled('DEFAULT_EXPORT_SETTINGS')
    def test_default_export_settings_standard_domain(self):
        """
        Verify STANDARD software plans do not have access to default export settings
        """
        self.update_subscription(SoftwarePlanEdition.STANDARD)
        settings = get_or_create_default_export_settings_for_domain(self.domain)
        self.assertIsNone(settings)

    @flag_enabled('DEFAULT_EXPORT_SETTINGS')
    def test_default_export_settings_pro_domain(self):
        """
        Verify PRO software plans do not have access to default export settings
        """
        self.update_subscription(SoftwarePlanEdition.PRO)
        settings = get_or_create_default_export_settings_for_domain(self.domain)
        self.assertIsNone(settings)

    @flag_enabled('DEFAULT_EXPORT_SETTINGS')
    def test_default_export_settings_advanced_domain(self):
        """
        Verify ADVANCED software plans do not have access to default export settings
        """
        self.update_subscription(SoftwarePlanEdition.ADVANCED)
        settings = get_or_create_default_export_settings_for_domain(self.domain)
        self.assertIsNone(settings)

    @flag_enabled('DEFAULT_EXPORT_SETTINGS')
    def test_default_export_settings_reseller_domain(self):
        """
        Verify RESELLER software plans do not have access to default export settings
        """
        self.update_subscription(SoftwarePlanEdition.RESELLER)
        settings = get_or_create_default_export_settings_for_domain(self.domain)
        self.assertIsNone(settings)

    @flag_enabled('DEFAULT_EXPORT_SETTINGS')
    def test_default_export_settings_managed_hosting_domain(self):
        """
        Verify MANAGED_HOSTING software plans do not have access to default export settings
        """
        self.update_subscription(SoftwarePlanEdition.MANAGED_HOSTING)
        settings = get_or_create_default_export_settings_for_domain(self.domain)
        self.assertIsNone(settings)

    @flag_enabled('DEFAULT_EXPORT_SETTINGS')
    def test_default_export_settings_enterprise_domain(self):
        """
        Verify software plan editions that do have access to default export settings
        are able to create a DefaultExportSettings instance
        """
        self.update_subscription(SoftwarePlanEdition.ENTERPRISE)
        settings = get_or_create_default_export_settings_for_domain(self.domain)
        self.assertIsNotNone(settings)
