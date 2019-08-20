from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import date
from django.test import TestCase
from custom.icds_reports.utils.data_accessor import get_inc_indicator_api_data


class NICIndicatorTest(TestCase):

    def test_file_content(self):
        self.maxDiff = None
        state_id = 'st1'
        month = '2017-05-01'
        data = get_inc_indicator_api_data(state_id, month)

        self.assertEqual(
            {'num_households_registered': 3633,
             'lactating_enrolled': 87,
             'ebf_in_month': 17,
             'children_enrolled': 618,
             'num_launched_awcs': 9,
             'state': u'st1',
             'pregnant_enrolled': 70,
             'cf_in_month': 14,
             'bf_at_birth': 1,
             'month': date(2017, 5, 1)},
            data
        )
