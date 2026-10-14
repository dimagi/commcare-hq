from datetime import date, timedelta

import pytest
from django.http import Http404
from django.test import TestCase, SimpleTestCase

from corehq.apps.accounting.models import SoftwarePlanEdition, Subscription, DefaultProductPlan, BillingAccount, \
    SubscriptionAdjustment
from corehq.apps.export.const import CASE_EXPORT, FORM_EXPORT
from corehq.apps.export.models import (
    CaseExportInstance,
    ExportColumn,
    FormExportInstance,
    TableConfiguration,
)
from corehq.apps.export.utils import (
    get_default_export_settings_if_available,
    get_export,
)
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
            DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.FREE),
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

    def test_default_export_settings_free_domain_returns_none(self):
        """
        Verify FREE software plans do not have access to default export settings
        """
        self.update_subscription(SoftwarePlanEdition.FREE)
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


class TestGetExport(TestCase):

    domain = 'get-export-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.form_export = FormExportInstance(domain=cls.domain, name='Forms')
        cls.case_export = CaseExportInstance(domain=cls.domain, name='Cases')
        cls.other_domain_export = FormExportInstance(domain='other-domain', name='Theirs')
        for export in [cls.form_export, cls.case_export, cls.other_domain_export]:
            export.save()
            cls.addClassCleanup(export.delete)

    def test_form_export(self):
        export = get_export(FORM_EXPORT, self.domain, self.form_export._id)
        assert export._id == self.form_export._id

    def test_case_export(self):
        export = get_export(CASE_EXPORT, self.domain, self.case_export._id)
        assert export._id == self.case_export._id

    def test_export_in_another_domain(self):
        with pytest.raises(Http404):
            get_export(FORM_EXPORT, self.domain, self.other_domain_export._id)

    def test_export_of_another_type(self):
        with pytest.raises(Http404):
            get_export(FORM_EXPORT, self.domain, self.case_export._id)
