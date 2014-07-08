from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.models import CommtrackConfig, ConsumptionConfig, StockRestoreConfig
from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.commtrack.const import DAYS_IN_MONTH
from corehq.apps.consumption.shortcuts import set_default_consumption_for_domain


class CommTrackSettingsTest(TestCase):

    def testOTASettings(self):
        domain = bootstrap_domain()
        ct_settings = CommtrackConfig.for_domain(domain.name)
        ct_settings.consumption_config = ConsumptionConfig(
            min_transactions=10,
            min_window=20,
            optimal_window=60,
        )
        ct_settings.ota_restore_config = StockRestoreConfig(
            section_to_consumption_types={'stock': 'consumption'},
        )
        set_default_consumption_for_domain(domain.name, 5 * DAYS_IN_MONTH)
        restore_settings = ct_settings.get_ota_restore_settings()
        self.assertEqual(1, len(restore_settings.section_to_consumption_types))
        self.assertEqual('consumption', restore_settings.section_to_consumption_types['stock'])
        self.assertEqual(10, restore_settings.consumption_config.min_periods)
        self.assertEqual(20, restore_settings.consumption_config.min_window)
        self.assertEqual(60, restore_settings.consumption_config.max_window)
        self.assertEqual(150, restore_settings.consumption_config.default_monthly_consumption_function('foo', 'bar'))
        self.assertFalse(restore_settings.force_consumption_case_filter(CommCareCase(type='force-type')))
        self.assertEqual(0, len(restore_settings.default_product_list))

        ct_settings.ota_restore_config.force_consumption_case_types=['force-type']
        ct_settings.ota_restore_config.use_dynamic_product_list=True
        restore_settings = ct_settings.get_ota_restore_settings()
        self.assertTrue(restore_settings.force_consumption_case_filter(CommCareCase(type='force-type')))
        self.assertEqual(3, len(restore_settings.default_product_list))
