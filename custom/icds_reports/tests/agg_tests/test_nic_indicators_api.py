from datetime import datetime, date
from freezegun import freeze_time

from django.test import TestCase
from custom.icds_reports.utils.data_accessor import get_inc_indicator_api_data
from custom.icds_reports.reports.mwcd_indicators import get_mwcd_indicator_api_data


@freeze_time("2017-05-02")
class NICIndicatorTest(TestCase):

    def test_file_content(self):
        get_inc_indicator_api_data.clear()
        data = get_inc_indicator_api_data()
        self.assertCountEqual(
            {'scheme_code': 'C002',
             'total_launched_awcs': 20,
             'dataarray1': [
                 {
                     'state_name': 'st2',
                     'site_id': 'st2',
                     'month': date(2017, 5, 1),
                     'num_launched_awcs': 11,
                     'num_households_registered': 3331,
                     'pregnant_enrolled': 85,
                     'lactating_enrolled': 79,
                     'children_enrolled': 669,
                     'bf_at_birth': 1,
                     'ebf_in_month': 11,
                     'cf_in_month': 20
                 },
                 {
                     'state_name': 'st1',
                     'site_id': 'st1',
                     'month': date(2017, 5, 1),
                     'num_launched_awcs': 9,
                     'num_households_registered': 3633,
                     'pregnant_enrolled': 70,
                     'lactating_enrolled': 87,
                     'children_enrolled': 618,
                     'bf_at_birth': 1,
                     'ebf_in_month': 17,
                     'cf_in_month': 14
                 }
             ]},
            data
        )

    def test_mwcd_indicators_data(self):
        self.maxDiff = None
        data = get_mwcd_indicator_api_data(date(2017, 4, 1))

        self.assertCountEqual([{'state_name': 'ALL INDIA', 'state_id': '0', 'num_launched_awcs': 21,
                                'num_launched_districts': 3, 'num_launched_states': 2, 'num_ls_launched': 6,
                                'awc_with_gm_devices': 25, 'cases_household': 2798, 'total_mothers': 321,
                                'cases_child_health': 1286}, {'state_name': 'st2', 'state_id': 'st2',
                                                              'num_launched_awcs': 11, 'num_launched_districts': 2,
                                                              'num_launched_states': 1, 'num_ls_launched': 2,
                                                              'awc_with_gm_devices': 11, 'cases_household': 1476,
                                                              'total_mothers': 164, 'cases_child_health': 668},
                               {'state_name': 'st1', 'state_id': 'st1', 'num_launched_awcs': 10,
                                'num_launched_districts': 1, 'num_launched_states': 1, 'num_ls_launched': 4,
                                'awc_with_gm_devices': 14, 'cases_household': 1322, 'total_mothers': 157,
                                'cases_child_health': 618}],
                              data['implementation_status']['dataarray'])

        self.assertCountEqual([{'state_name': 'st1', 'state_id': 'st1', 'month': 4, 'total_mothers': 134,
                                'num_launched_awcs': 10, 'cases_child_health': 608, 'year': 2017},
                               {'state_name': 'st2', 'state_id': 'st2', 'month': 4, 'total_mothers': 129,
                                'num_launched_awcs': 11, 'cases_child_health': 653, 'year': 2017},
                               {'state_name': 'st1', 'state_id': 'st1', 'month': 5, 'total_mothers': 157,
                                'num_launched_awcs': 10, 'cases_child_health': 618, 'year': 2017},
                               {'state_name': 'st2', 'state_id': 'st2', 'month': 5, 'total_mothers': 164,
                                'num_launched_awcs': 11, 'cases_child_health': 668, 'year': 2017},
                               {'month': 4, 'num_launched_awcs': 21, 'total_mothers': 263,
                                'cases_child_health': 1261, 'state_name': 'ALL INDIA',
                                'state_id': '0', 'year': 2017},
                               {'month': 5, 'num_launched_awcs': 21, 'total_mothers': 321,
                                'cases_child_health': 1286, 'state_name': 'ALL INDIA',
                                'state_id': '0', 'year': 2017}],
                              data['monthly_trend']['dataarray'])
