
from datetime import datetime, date
from freezegun import freeze_time

from django.test import TestCase
from custom.icds_reports.utils.data_accessor import get_inc_indicator_api_data
from mock import mock


@freeze_time("2017-05-02")
class NICIndicatorTest(TestCase):

    def test_file_content(self):
        get_inc_indicator_api_data.clear(use_citus=True)
        data = get_inc_indicator_api_data()
        self.assertEqual(
            {'scheme_code': 'C002',
             'total_launched_awcs': 20,
             'dataarray1': [
                 {
                     'state_name': 'st2',
                     'state_site_code': 'st2',
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
                     'state_site_code': 'st1',
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
