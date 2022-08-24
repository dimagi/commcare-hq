from datetime import date, timedelta

from django.test import TestCase, SimpleTestCase

from corehq.apps.accounting.models import SoftwarePlanEdition, Subscription, DefaultProductPlan, BillingAccount, \
    SubscriptionAdjustment
from corehq.apps.export.models import FormExportInstance, TableConfiguration, ExportColumn
from corehq.apps.export.utils import get_default_export_settings_if_available
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.tests import generator
from corehq.apps.export.views.utils import clean_odata_columns


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


class TestOdataFeedUtils(SimpleTestCase):

    def test_clean_odata_columns(self):
        export_instance = FormExportInstance(
            _id='config_id',
            tables=[TableConfiguration(columns=[
                ExportColumn(
                    label='@label_reserved_character_01',
                ),
                ExportColumn(
                    label='label.reserved.character.02',
                ),
                ExportColumn(
                    label='label_reserved_character_03\n',
                ),
                ExportColumn(
                    label='label_reserved_character_04\t',
                ),
                ExportColumn(
                    label='#label_reserved_character_05',
                ),
                ExportColumn(
                    label='label,reserved,character,06',
                ),
                ExportColumn(
                    label='formid',
                    is_deleted=True,
                ),
            ])],
            domain='test_odata_domain'
        )

        clean_odata_columns(export_instance)

        self.assertEqual(export_instance.tables[0].columns[0].label, 'label_reserved_character_01')
        self.assertEqual(export_instance.tables[0].columns[1].label, 'label reserved character 02')
        self.assertEqual(export_instance.tables[0].columns[2].label, 'label_reserved_character_03')
        self.assertEqual(export_instance.tables[0].columns[3].label, 'label_reserved_character_04 ')
        self.assertEqual(export_instance.tables[0].columns[4].label, 'label_reserved_character_05')
        self.assertEqual(export_instance.tables[0].columns[5].label, 'labelreservedcharacter06')
        self.assertEqual(export_instance.tables[0].columns[6].label, 'formid_deleted')
