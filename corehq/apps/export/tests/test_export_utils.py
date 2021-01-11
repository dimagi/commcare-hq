from datetime import datetime, timedelta

from django.test import TestCase

from corehq.apps.accounting.models import SoftwarePlanEdition, Subscription, DefaultProductPlan, BillingAccount
from corehq.apps.domain.models import Domain
from corehq.apps.export.utils import get_or_create_default_export_settings_for_domain
from corehq.util.test_utils import flag_enabled


class TestExportUtils(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestExportUtils, cls).setUpClass()
        cls.domain = Domain(name='test-export-utils')
        cls.domain.save()
        cls.account = BillingAccount.get_or_create_account_by_domain(
            cls.domain.name,
            created_by='test'
        )[0]
        cls.account.save()

    @classmethod
    def tearDownClass(cls):
        cls.account.delete()
        cls.domain.delete()
        super(TestExportUtils, cls).tearDownClass()

    def _create_subscription(self, plan):
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, DefaultProductPlan.get_default_plan_version(plan),
            date_start=datetime.now() - timedelta(days=3)
        )
        subscription.is_active = True
        subscription.save()

    @flag_enabled('DEFAULT_EXPORT_SETTINGS')
    def test_default_export_settings_no_ff_enabled(self):
        """
        Default export settings are only available if FF is enabled
        """
        self._create_subscription(SoftwarePlanEdition.ENTERPRISE)
        settings = get_or_create_default_export_settings_for_domain(self.domain)

        self.assertIsNone(settings)

    @flag_enabled('DEFAULT_EXPORT_SETTINGS')
    def test_default_export_settings_non_enterprise_domain(self):
        """
        Default export settings are only available for enterprise domains
        """
        self._create_subscription(SoftwarePlanEdition.ADVANCED)
        settings = get_or_create_default_export_settings_for_domain(self.domain)
        self.assertIsNone(settings)

    def test_default_export_settings_enterprise_domain(self):
        """
        Default export settings are only available for enterprise domains
        """
        self._create_subscription(SoftwarePlanEdition.ENTERPRISE)
        settings = get_or_create_default_export_settings_for_domain(self.domain)
        self.assertIsNotNone(settings)

    def test_default_export_settings_default_values(self):
        """
        Ensure default values are what we expect
        """
        self._create_subscription(SoftwarePlanEdition.ENTERPRISE)
        settings = get_or_create_default_export_settings_for_domain(self.domain)
        self.assertIsNotNone(settings)
