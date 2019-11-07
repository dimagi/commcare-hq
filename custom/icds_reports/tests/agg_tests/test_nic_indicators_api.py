from datetime import datetime, date
from freezegun import freeze_time

from django.test import TestCase
from custom.icds_reports.utils.data_accessor import get_inc_indicator_api_data
from custom.icds_reports.reports.mwcd_indicators import get_mwcd_indicator_api_data


@freeze_time("2017-05-02")
class NICIndicatorTest(TestCase):

    def test_file_content(self):
        get_inc_indicator_api_data.clear(use_citus=True)
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
        data = get_mwcd_indicator_api_data(date(2017, 4, 1))
        print(data)
        self.assertCountEqual({"scheme_code": "C002",
                               "implementation_status": {
                                   "national_total": {
                                       "nation_code": 0,
                                       "num_launched_awcs": 0,
                                       "num_launched_districts": 0,
                                       "num_launched_states": 0,
                                       "num_ls_launched": 0,
                                       "awc_with_gm_devices": 0,
                                       "cases_household": 0,
                                       "total_mothers": 0,
                                       "cases_child_health": 0
                                   },
                                   "dataarray": [
                                       {
                                           "state_name": "st1",
                                           "state_id": "st1",
                                           "num_launched_awcs": 0,
                                           "num_launched_districts": 0,
                                           "num_launched_states": 0,
                                           "num_ls_launched": 0,
                                           "awc_with_gm_devices": 0,
                                           "cases_household": 0,
                                           "total_mothers": 0,
                                           "cases_child_health": 0
                                       }
                                   ]
                               },
                               "monthly_trend": {
                                   "national_total": [
                                       {
                                           "month": 10,
                                           "total_awc_launched": 0,
                                           "total_mothers": 0,
                                           "total_children": 0,
                                           "year": 2019},
                                       {
                                           "month": 11,
                                           "total_awc_launched": 0,
                                           "total_mothers": 0,
                                           "total_children": 0,
                                           "year": 2019
                                       }
                                   ],
                                   "dataarray": [
                                       {
                                           "state_name": "st1",
                                           "state_id": "st1",
                                           "month": 10,
                                           "total_mothers": 0,
                                           "num_launched_awcs": 0,
                                           "cases_child_health": 0,
                                           "year": 2019},
                                       {
                                           "state_name": "st1",
                                           "state_id": "st1",
                                           "month": 11,
                                           "total_mothers": 0,
                                           "num_launched_awcs": 0,
                                           "cases_child_health": 0,
                                           "year": 2019
                                       }
                                   ]
                               }}, data)
