from __future__ import absolute_import

from __future__ import unicode_literals
from datetime import datetime

from django.test.utils import override_settings
from django.test import TestCase

from custom.icds_reports.reports.issnip_monthly_register import ISSNIPMonthlyReport
import mock


@override_settings(SERVER_ENVIRONMENT='icds')
class TestInstitutionalDeliveriesSector(TestCase):

    def test_agg_awc_monthly_data(self):
        config = {
            'awc_id': ['a48'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='a48'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)[0]['agg_awc_monthly_data']
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
        self.assertEqual(data['cases_person_referred'], 0)
        self.assertEqual(data['aww_name'], 'aww_name48')
        self.assertEqual(data['contact_phone_number'], '91552222')
        self.assertEqual(data['num_anc_visits'], 0)
        self.assertIsNone(data['num_children_immunized'])

    def test_child_health_monthly_data(self):
        config = {
            'awc_id': ['a48'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='a48'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)[0]['child_health_monthly_data']
        self.assertEqual(data['infants_0_6'], 4)
        self.assertEqual(data['children_6_36'], 9)
        self.assertEqual(data['children_36_72'], 38)
        self.assertEqual(data['normal_children_breakfast_and_hcm'], 25)
        self.assertEqual(data['normal_children_thr'], 8)
        self.assertEqual(data['severely_underweight_children_breakfast_and_hcm'], 0)
        self.assertEqual(data['severely_underweight_children_thr'], 1)

    def test_css_record_monthly(self):
        config = {
            'awc_id': ['a48'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='a48'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)[0]['css_record_monthly']
        self.assertEqual(data['pregnant_women_thr'], 5)
        self.assertEqual(data['lactating_women_thr'], 7)

    def test_vhnd_data(self):
        config = {
            'awc_id': ['a48'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='a48'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)[0]['vhnd_data']
        self.assertEqual(data['vhsnd_date_past_month'], datetime(2017, 5, 13).date())
        self.assertEqual(data['local_leader'], 1)
        self.assertEqual(data['aww_present'], 1)

    def test_ccs_record_monthly_ucr(self):
        config = {
            'awc_id': ['a48'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='a48'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)[0]['agg_ccs_record_monthly']
        self.assertEqual(data['sc_pregnant'], 0)
        self.assertEqual(data['st_pregnant'], 0)
        self.assertEqual(data['obc_pregnant'], 0)
        self.assertEqual(data['general_pregnant'], 0)
        self.assertEqual(data['total_pregnant'], 0)
        self.assertEqual(data['sc_lactating'], 0)
        self.assertEqual(data['st_lactating'], 0)
        self.assertEqual(data['obc_lactating'], 4)
        self.assertEqual(data['general_lactating'], 0)
        self.assertEqual(data['total_lactating'], 4)
        self.assertEqual(data['minority_pregnant'], 0)
        self.assertEqual(data['minority_lactating'], 4)

    def test_agg_child_health_monthly(self):
        config = {
            'awc_id': ['a3'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='a3'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)[0]['agg_child_health_monthly']
        self.assertEqual(data['boys_normal_0_3'], 1)
        self.assertEqual(data['girls_normal_0_3'], 1)
        self.assertEqual(data['boys_normal_3_5'], 7)
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

    def test_child_health_monthly(self):
        config = {
            'awc_id': ['a3'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='a3'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)[0]['child_health_monthly']

        self.assertEquals(data['obc_boys_48_72'], 0)
        self.assertEquals(data['general_boys_48_72'], 0)
        self.assertEquals(data['total_boys_48_72'], 0)
        self.assertEquals(data['general_girls_48_72'], 0)
        self.assertEquals(data['st_boys_48_72'], 0)
        self.assertEquals(data['total_girls_48_72'], 0)
        self.assertEquals(data['minority_girls_48_72_num'], 0)
        self.assertEquals(data['obc_girls_48_72'], 0)
        self.assertEquals(data['sc_girls_48_72'], 0)
        self.assertEquals(data['sc_boys_48_72'], 0)
        self.assertEquals(data['minority_boys_48_72_num'], 0)

        self.assertEqual(data['pre_sc_boys_48_72'], 0)
        self.assertEqual(data['pre_sc_girls_48_72'], 0)
        self.assertEqual(data['pre_st_boys_48_72'], 1)
        self.assertEqual(data['pre_st_girls_48_72'], 0)
        self.assertEqual(data['pre_obc_boys_48_72'], 3)
        self.assertEqual(data['pre_obc_girls_48_72'], 3)
        self.assertEqual(data['pre_general_boys_48_72'], 0)
        self.assertEqual(data['pre_general_girls_48_72'], 0)
        self.assertEqual(data['pre_total_boys_48_72'], 4)
        self.assertEqual(data['pre_total_girls_48_72'], 3)
        self.assertEqual(data['pre_minority_boys_48_72'], 0)
        self.assertEqual(data['pre_minority_girls_48_72'], 0)

    def test_agg_awc_monthly_data_multiple_locations(self):
        config = {
            'awc_id': ['a48', 'a3'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='some awc'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)
            data_a48 = data[0]['agg_awc_monthly_data']
            data_a3 = data[1]['agg_awc_monthly_data']
        self.assertEqual(data_a48['block_name'], 'b4')
        self.assertEqual(data_a48['awc_name'], 'a48')
        self.assertEqual(data_a48['awc_site_code'], 'a48')
        self.assertIsNone(data_a48['infra_type_of_building'])
        self.assertEqual(data_a48['infra_clean_water'], 1)
        self.assertEqual(data_a48['cases_ccs_pregnant_all'], 5)
        self.assertEqual(data_a48['cases_ccs_lactating_all'], 7)
        self.assertEqual(data_a48['awc_days_open'], 14)
        self.assertIsNone(data_a48['awc_days_pse_conducted'])
        self.assertEqual(data_a48['usage_num_home_visit'], 0)
        self.assertEqual(data_a48['cases_person_referred'], 0)
        self.assertEqual(data_a48['aww_name'], 'aww_name48')
        self.assertEqual(data_a48['contact_phone_number'], '91552222')
        self.assertEqual(data_a48['num_anc_visits'], 0)
        self.assertIsNone(data_a48['num_children_immunized'])

        self.assertEqual(data_a3['block_name'], 'b2')
        self.assertEqual(data_a3['awc_name'], 'a3')
        self.assertEqual(data_a3['awc_site_code'], 'a3')
        self.assertEqual(data_a3['infra_type_of_building'], 'pucca')
        self.assertEqual(data_a3['infra_clean_water'], 1)
        self.assertEqual(data_a3['cases_ccs_pregnant_all'], 2)
        self.assertEqual(data_a3['cases_ccs_lactating_all'], 2)
        self.assertEqual(data_a3['awc_days_open'], 23)
        self.assertIsNone(data_a3['awc_days_pse_conducted'])
        self.assertEqual(data_a3['usage_num_home_visit'], 2)
        self.assertEqual(data_a3['cases_person_referred'], 0)
        self.assertIsNone(data_a3['aww_name'])
        self.assertIsNone(data_a3['contact_phone_number'])
        self.assertEqual(data_a3['num_anc_visits'], 0)
        self.assertIsNone(data_a3['num_children_immunized'])

    def test_child_health_monthly_data_multiple_locations(self):
        config = {
            'awc_id': ['a48', 'a3'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='some value'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)[0]['child_health_monthly_data']
        self.assertEqual(data['infants_0_6'], 4)
        self.assertEqual(data['children_6_36'], 9)
        self.assertEqual(data['children_36_72'], 38)
        self.assertEqual(data['normal_children_breakfast_and_hcm'], 25)
        self.assertEqual(data['normal_children_thr'], 8)
        self.assertEqual(data['severely_underweight_children_breakfast_and_hcm'], 0)
        self.assertEqual(data['severely_underweight_children_thr'], 1)

    def test_css_record_monthly_multiple_locations(self):
        config = {
            'awc_id': ['a48', 'a3'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='some value'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)
            data_a48 = data[0]['css_record_monthly']
            data_a3 = data[1]['css_record_monthly']
        self.assertEqual(data_a48['pregnant_women_thr'], 5)
        self.assertEqual(data_a48['lactating_women_thr'], 7)
        self.assertEqual(data_a3['pregnant_women_thr'], 2)
        self.assertEqual(data_a3['lactating_women_thr'], 2)

    def test_vhnd_data_multiple_locations(self):
        config = {
            'awc_id': ['a48', 'a3'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='a48'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)
            data_a48 = data[0]['vhnd_data']
            data_a3 = data[1]['vhnd_data']

        self.assertEqual(data_a48['vhsnd_date_past_month'], datetime(2017, 5, 13).date())
        self.assertEqual(data_a48['local_leader'], 1)
        self.assertEqual(data_a48['aww_present'], 1)

        self.assertEqual(data_a3['vhsnd_date_past_month'], datetime(2017, 5, 5).date())
        self.assertEqual(data_a3['local_leader'], 0)
        self.assertEqual(data_a3['aww_present'], 1)

    def test_ccs_record_monthly_ucr_multiple_locations(self):
        config = {
            'awc_id': ['a48', 'a3'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='a48'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)
            data_a48 = data[0]['agg_ccs_record_monthly']
            data_a3 = data[1]['agg_ccs_record_monthly']
        self.assertEqual(data_a48['sc_pregnant'], 0)
        self.assertEqual(data_a48['st_pregnant'], 0)
        self.assertEqual(data_a48['obc_pregnant'], 0)
        self.assertEqual(data_a48['general_pregnant'], 0)
        self.assertEqual(data_a48['total_pregnant'], 0)
        self.assertEqual(data_a48['sc_lactating'], 0)
        self.assertEqual(data_a48['st_lactating'], 0)
        self.assertEqual(data_a48['obc_lactating'], 4)
        self.assertEqual(data_a48['general_lactating'], 0)
        self.assertEqual(data_a48['total_lactating'], 4)
        self.assertEqual(data_a48['minority_pregnant'], 0)
        self.assertEqual(data_a48['minority_lactating'], 4)

        self.assertEqual(data_a3['sc_pregnant'], 1)
        self.assertEqual(data_a3['st_pregnant'], 0)
        self.assertEqual(data_a3['obc_pregnant'], 0)
        self.assertEqual(data_a3['general_pregnant'], 0)
        self.assertEqual(data_a3['total_pregnant'], 1)
        self.assertEqual(data_a3['sc_lactating'], 0)
        self.assertEqual(data_a3['st_lactating'], 1)
        self.assertEqual(data_a3['obc_lactating'], 1)
        self.assertEqual(data_a3['general_lactating'], 0)
        self.assertEqual(data_a3['total_lactating'], 2)
        self.assertEqual(data_a3['minority_pregnant'], 0)
        self.assertEqual(data_a3['minority_lactating'], 0)

    def test_agg_child_health_monthly_multiple_locations(self):
        config = {
            'awc_id': ['a48', 'a3'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='a48'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)
            data_a48 = data[0]['agg_child_health_monthly']
            data_a3 = data[1]['agg_child_health_monthly']

        self.assertEqual(data_a48['boys_normal_0_3'], 0)
        self.assertEqual(data_a48['girls_normal_0_3'], 0)
        self.assertEqual(data_a48['boys_normal_3_5'], 0)
        self.assertEqual(data_a48['girls_normal_3_5'], 0)
        self.assertEqual(data_a48['boys_moderately_0_3'], 0)
        self.assertEqual(data_a48['girls_moderately_0_3'], 0)
        self.assertEqual(data_a48['boys_moderately_3_5'], 0)
        self.assertEqual(data_a48['girls_moderately_3_5'], 0)
        self.assertEqual(data_a48['boys_severely_0_3'], 0)
        self.assertEqual(data_a48['girls_severely_0_3'], 0)
        self.assertEqual(data_a48['boys_severely_3_5'], 0)
        self.assertEqual(data_a48['girls_severely_3_5'], 0)
        self.assertEqual(data_a48['boys_stunted_0_3'], 0)
        self.assertEqual(data_a48['girls_stunted_0_3'], 0)
        self.assertEqual(data_a48['boys_stunted_3_5'], 0)
        self.assertEqual(data_a48['girls_stunted_3_5'], 0)
        self.assertEqual(data_a48['boys_wasted_0_3'], 0)
        self.assertEqual(data_a48['girls_wasted_0_3'], 0)
        self.assertEqual(data_a48['boys_wasted_3_5'], 0)
        self.assertEqual(data_a48['girls_wasted_3_5'], 0)
        self.assertEqual(data_a48['sc_boys_6_36'], 0)
        self.assertEqual(data_a48['sc_girls_6_36'], 0)
        self.assertEqual(data_a48['st_boys_6_36'], 0)
        self.assertEqual(data_a48['st_girls_6_36'], 0)
        self.assertEqual(data_a48['obc_boys_6_36'], 3)
        self.assertEqual(data_a48['obc_girls_6_36'], 2)
        self.assertEqual(data_a48['general_boys_6_36'], 0)
        self.assertEqual(data_a48['general_girls_6_36'], 0)
        self.assertEqual(data_a48['total_boys_6_36'], 3)
        self.assertEqual(data_a48['total_girls_6_36'], 2)
        self.assertEqual(data_a48['minority_boys_6_36_num'], 3)
        self.assertEqual(data_a48['minority_girls_6_36_num'], 2)

        self.assertEqual(data_a3['boys_normal_0_3'], 1)
        self.assertEqual(data_a3['girls_normal_0_3'], 1)
        self.assertEqual(data_a3['boys_normal_3_5'], 7)
        self.assertEqual(data_a3['girls_normal_3_5'], 7)
        self.assertEqual(data_a3['boys_moderately_0_3'], 1)
        self.assertEqual(data_a3['girls_moderately_0_3'], 0)
        self.assertEqual(data_a3['boys_moderately_3_5'], 2)
        self.assertEqual(data_a3['girls_moderately_3_5'], 0)
        self.assertEqual(data_a3['boys_severely_0_3'], 0)
        self.assertEqual(data_a3['girls_severely_0_3'], 0)
        self.assertEqual(data_a3['boys_severely_3_5'], 0)
        self.assertEqual(data_a3['girls_severely_3_5'], 0)
        self.assertEqual(data_a3['boys_stunted_0_3'], 0)
        self.assertEqual(data_a3['girls_stunted_0_3'], 0)
        self.assertEqual(data_a3['boys_stunted_3_5'], 0)
        self.assertEqual(data_a3['girls_stunted_3_5'], 0)
        self.assertEqual(data_a3['boys_wasted_0_3'], 0)
        self.assertEqual(data_a3['girls_wasted_0_3'], 0)
        self.assertEqual(data_a3['boys_wasted_3_5'], 0)
        self.assertEqual(data_a3['girls_wasted_3_5'], 0)
        self.assertEqual(data_a3['sc_boys_6_36'], 0)
        self.assertEqual(data_a3['sc_girls_6_36'], 0)
        self.assertEqual(data_a3['st_boys_6_36'], 0)
        self.assertEqual(data_a3['st_girls_6_36'], 0)
        self.assertEqual(data_a3['obc_boys_6_36'], 0)
        self.assertEqual(data_a3['obc_girls_6_36'], 0)
        self.assertEqual(data_a3['general_boys_6_36'], 0)
        self.assertEqual(data_a3['general_girls_6_36'], 0)
        self.assertEqual(data_a3['total_boys_6_36'], 0)
        self.assertEqual(data_a3['total_girls_6_36'], 0)
        self.assertEqual(data_a3['minority_boys_6_36_num'], 0)
        self.assertEqual(data_a3['minority_girls_6_36_num'], 0)

    def test_child_health_monthly_multiple_locations(self):
        config = {
            'awc_id': ['a48', 'a3'],
            'month': datetime(2017, 5, 1).date(),
            'domain': 'icds-cas'
        }
        with mock.patch('custom.icds_reports.reports.issnip_monthly_register.ISSNIPMonthlyReport.get_awc_name',
                        return_value='some name'):
            data = list(ISSNIPMonthlyReport(config=config).to_pdf_format)
            data_a48 = data[0]['child_health_monthly']
            data_a3 = data[1]['child_health_monthly']

        self.assertEquals(data_a48['obc_boys_48_72'], 0)
        self.assertEquals(data_a48['general_boys_48_72'], 0)
        self.assertEquals(data_a48['total_boys_48_72'], 0)
        self.assertEquals(data_a48['general_girls_48_72'], 0)
        self.assertEquals(data_a48['st_boys_48_72'], 0)
        self.assertEquals(data_a48['total_girls_48_72'], 0)
        self.assertEquals(data_a48['minority_girls_48_72_num'], 0)
        self.assertEquals(data_a48['obc_girls_48_72'], 0)
        self.assertEquals(data_a48['sc_girls_48_72'], 0)
        self.assertEquals(data_a48['sc_boys_48_72'], 0)
        self.assertEquals(data_a48['minority_boys_48_72_num'], 0)

        self.assertEqual(data_a48['pre_sc_boys_48_72'], 0)
        self.assertEqual(data_a48['pre_sc_girls_48_72'], 0)
        self.assertEqual(data_a48['pre_st_boys_48_72'], 0)
        self.assertEqual(data_a48['pre_st_girls_48_72'], 0)
        self.assertEqual(data_a48['pre_obc_boys_48_72'], 0)
        self.assertEqual(data_a48['pre_obc_girls_48_72'], 0)
        self.assertEqual(data_a48['pre_general_boys_48_72'], 0)
        self.assertEqual(data_a48['pre_general_girls_48_72'], 0)
        self.assertEqual(data_a48['pre_total_boys_48_72'], 0)
        self.assertEqual(data_a48['pre_total_girls_48_72'], 0)
        self.assertEqual(data_a48['pre_minority_boys_48_72'], 0)
        self.assertEqual(data_a48['pre_minority_girls_48_72'], 0)

        self.assertEquals(data_a3['obc_boys_48_72'], 0)
        self.assertEquals(data_a3['general_boys_48_72'], 0)
        self.assertEquals(data_a3['total_boys_48_72'], 0)
        self.assertEquals(data_a3['general_girls_48_72'], 0)
        self.assertEquals(data_a3['st_boys_48_72'], 0)
        self.assertEquals(data_a3['total_girls_48_72'], 0)
        self.assertEquals(data_a3['minority_girls_48_72_num'], 0)
        self.assertEquals(data_a3['obc_girls_48_72'], 0)
        self.assertEquals(data_a3['sc_girls_48_72'], 0)
        self.assertEquals(data_a3['sc_boys_48_72'], 0)
        self.assertEquals(data_a3['minority_boys_48_72_num'], 0)

        self.assertEqual(data_a3['pre_sc_boys_48_72'], 0)
        self.assertEqual(data_a3['pre_sc_girls_48_72'], 0)
        self.assertEqual(data_a3['pre_st_boys_48_72'], 1)
        self.assertEqual(data_a3['pre_st_girls_48_72'], 0)
        self.assertEqual(data_a3['pre_obc_boys_48_72'], 3)
        self.assertEqual(data_a3['pre_obc_girls_48_72'], 3)
        self.assertEqual(data_a3['pre_general_boys_48_72'], 0)
        self.assertEqual(data_a3['pre_general_girls_48_72'], 0)
        self.assertEqual(data_a3['pre_total_boys_48_72'], 4)
        self.assertEqual(data_a3['pre_total_girls_48_72'], 3)
        self.assertEqual(data_a3['pre_minority_boys_48_72'], 0)
        self.assertEqual(data_a3['pre_minority_girls_48_72'], 0)
