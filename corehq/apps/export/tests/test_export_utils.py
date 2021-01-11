from datetime import date, timedelta

from django.test import TestCase

from corehq.apps.accounting.models import SoftwarePlanEdition, Subscription, DefaultProductPlan, BillingAccount
from corehq.apps.domain.models import Domain
from corehq.apps.export.utils import get_or_create_default_export_settings_for_domain
from corehq.util.test_utils import flag_enabled


class TestExportUtils(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestExportUtils, cls).setUpClass()
        cls.domain = Domain.get_or_create_with_name('test-export-utils', is_active=True)
        cls.account, _ = BillingAccount.get_or_create_account_by_domain(
            cls.domain.name,
            created_by='webuser@test.com'
        )
        cls.account.save()
        cls.subscription = Subscription.new_domain_subscription(
            cls.account, cls.domain.name,
            DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ENTERPRISE),
            date_start=date.today() - timedelta(days=3)
        )
        cls.subscription.is_active = True
        cls.subscription.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(TestExportUtils, cls).tearDownClass()

    def update_subscription(self, plan):
        if self.subscription.plan_version.plan.edition != plan:
            self.subscription.change_plan(DefaultProductPlan.get_default_plan_version(plan))
            self.subscription.save()

    def test_default_export_settings_no_ff_enabled(self):
        """
        Default export settings are only available if the feature flag is enabled
        NOTE: no decorator to enable DEFAULT_EXPORT_SETTINGS feature flag
        """
        self.update_subscription(SoftwarePlanEdition.ENTERPRISE)
        settings = get_or_create_default_export_settings_for_domain(self.domain)
        self.assertIsNone(settings)

    @flag_enabled('DEFAULT_EXPORT_SETTINGS')
    def test_default_export_settings_non_enterprise_domain(self):
        """
        Verify software plan editions that do not have access to default export settings
        are not able to create a DefaultExportSettings instance
        """
        def test(plan_edition):
            self.update_subscription(plan_edition)
            settings = get_or_create_default_export_settings_for_domain(self.domain)
            self.assertIsNone(settings)

        yield test, SoftwarePlanEdition.COMMUNITY
        yield test, SoftwarePlanEdition.STANDARD
        yield test, SoftwarePlanEdition.PRO
        yield test, SoftwarePlanEdition.ADVANCED
        yield test, SoftwarePlanEdition.RESELLER
        yield test, SoftwarePlanEdition.MANAGED_HOSTING

    @flag_enabled('DEFAULT_EXPORT_SETTINGS')
    def test_default_export_settings_enterprise_domain(self):
        """
        Verify software plan editions that do have access to default export settings
        are able to create a DefaultExportSettings instance
        """
        self.update_subscription(SoftwarePlanEdition.ENTERPRISE)
        settings = get_or_create_default_export_settings_for_domain(self.domain)
        self.assertIsNotNone(settings)
