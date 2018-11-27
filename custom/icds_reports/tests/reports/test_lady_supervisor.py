from __future__ import absolute_import

from __future__ import unicode_literals
from django.test import TestCase

from custom.icds_reports.messages import lady_supervisor_number_of_awcs_visited_help_text, \
    lady_supervisor_number_of_beneficiaries_visited_help_text, lady_supervisor_number_of_vhnds_observed_help_text
from custom.icds_reports.reports.lady_supervisor import get_lady_supervisor_data


class TestDemographics(TestCase):

    def test_number_of_awcs_visited_launched_data(self):
        data = get_lady_supervisor_data(
            'icds-cas',
            {
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'supervisor_id': 's1',
                'aggregation_level': 4,
            }
        )
        expected = {
            "redirect": "demographics/registered_household",
            "all": None,
            "format": "number",
            "color": "red",
            "percent": 0.0,
            "value": 6964,
            "label": "Registered Households",
            "frequency": "month",
            "help_text": "Total number of households registered"
        }
        self.assertDictEqual(expected, data['records'][0][0])
