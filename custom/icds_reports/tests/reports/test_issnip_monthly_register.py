from __future__ import absolute_import

from datetime import datetime

from django.test.utils import override_settings
from django.test import TestCase

from custom.icds_reports.reports.issnip_monthly_register import ISSNIPMonthlyReport


@override_settings(SERVER_ENVIRONMENT='icds')
class TestInstitutionalDeliveriesSector(TestCase):

    def test_agg_awc_monthly_data(self):
        config = {
            'awc_id': 'a48',
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        data = ISSNIPMonthlyReport(config=config).agg_awc_monthly_data
        self.assertEqual(data['block_name'], 'b4')
        self.assertEqual(data['awc_name'], 'a48')
        self.assertEqual(data['awc_site_code'], 'a48')
        self.assertIsNone(data['infra_type_of_building'])
        self.assertEqual(data['infra_clean_water'], 1)
        self.assertEqual(data['cases_ccs_pregnant_all'], 5)
        self.assertEqual(data['cases_ccs_lactating_all'], 7)
        self.assertEqual(data['awc_days_open'], 14)
        self.assertIsNone(data['awc_days_pse_conducted'])
        self.assertEqual(data['usage_num_home_visit'], 0)
        self.assertIsNone(data['ls_awc_present'])
        self.assertEqual(data['cases_person_referred'], 0)

    def test_child_health_monthly_data(self):
        config = {
            'awc_id': 'a48',
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        data = ISSNIPMonthlyReport(config=config).child_health_monthly_data
        self.assertEqual(data['infants_0_6'], 4)
        self.assertEqual(data['children_6_36'], 9)
        self.assertEqual(data['children_36_72'], 38)
        self.assertEqual(data['normal_children_breakfast_and_hcm'], 25)
        self.assertEqual(data['normal_children_thr'], 8)
        self.assertEqual(data['severely_underweight_children_breakfast_and_hcm'], 0)
        self.assertEqual(data['severely_underweight_children_thr'], 1)

    def test_css_record_monthly(self):
        config = {
            'awc_id': 'a48',
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        data = ISSNIPMonthlyReport(config=config).css_record_monthly
        self.assertEqual(data['pregnant_women_thr'], 17)
        self.assertEqual(data['lactating_women_thr'], 19)

    def test_vhnd_data(self):
        config = {
            'awc_id': 'a48',
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        data = ISSNIPMonthlyReport(config=config).vhnd_data
        self.assertEqual(data['vhsnd_date_past_month'], datetime(2017, 5, 13).date())
        self.assertEquals(data['local_leader'], 1)

    def test_ccs_record_monthly_ucr(self):
        config = {
            'awc_id': 'a48',
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        data = ISSNIPMonthlyReport(config=config).ccs_record_monthly_ucr
        self.assertEqual(data['obc_lactating'], 4)
        self.assertEqual(data['total_lactating'], 4)
        self.assertEqual(data['minority_lactating'], 4)

    def test_child_health_monthly_ucr(self):
        config = {
            'awc_id': 'a3',
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        data = ISSNIPMonthlyReport(config=config).child_health_monthly_ucr
        self.assertEqual(data['pre_st_boys_36_72'], 1)
        self.assertEqual(data['pre_obc_boys_36_72'], 3)
        self.assertEqual(data['pre_obc_girls_36_72'], 3)
        self.assertEqual(data['pre_total_boys_36_72'], 4)
        self.assertEqual(data['pre_total_girls_36_72'], 3)

    def test_agg_child_health_monthly(self):
        config = {
            'awc_id': 'a3',
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        data = ISSNIPMonthlyReport(config=config).agg_child_health_monthly
        self.assertEqual(data['boys_normal_0_3'], 1)
        self.assertEqual(data['girls_normal_0_3'], 1)
        self.assertEqual(data['boys_normal_3_5'], 8)
        self.assertEqual(data['girls_normal_3_5'], 7)
        self.assertEqual(data['boys_moderately_0_3'], 1)
        self.assertEqual(data['girls_moderately_0_3'], 0)
        self.assertEqual(data['boys_moderately_3_5'], 2)
        self.assertEqual(data['girls_moderately_3_5'], 0)
        self.assertEqual(data['boys_severely_0_3'], 0)
        self.assertEqual(data['girls_severely_0_3'], 0)
        self.assertEqual(data['boys_severely_3_5'], 0)
        self.assertEqual(data['girls_severely_3_5'], 0)
        self.assertEqual(data['boys_stunted_0_3'], 0)
        self.assertEqual(data['girls_stunted_0_3'], 0)
        self.assertEqual(data['boys_stunted_3_5'], 0)
        self.assertEqual(data['girls_stunted_3_5'], 0)
        self.assertEqual(data['boys_wasted_0_3'], 0)
        self.assertEqual(data['girls_wasted_0_3'], 0)
        self.assertEqual(data['boys_wasted_3_5'], 0)
        self.assertEqual(data['girls_wasted_3_5'], 0)
        self.assertEqual(data['sc_boys_6_36'], 0)
        self.assertEqual(data['sc_girls_6_36'], 0)
        self.assertEqual(data['st_boys_6_36'], 0)
        self.assertEqual(data['st_girls_6_36'], 0)
        self.assertEqual(data['obc_boys_6_36'], 0)
        self.assertEqual(data['obc_girls_6_36'], 0)
        self.assertEqual(data['general_boys_6_36'], 0)
        self.assertEqual(data['general_girls_6_36'], 0)
        self.assertEqual(data['total_boys_6_36'], 0)
        self.assertEqual(data['total_girls_6_36'], 0)
        self.assertEqual(data['minority_boys_6_36_num'], 0)
        self.assertEqual(data['minority_girls_6_36_num'], 0)
