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
            'all': None,
            'format': 'number',
            'percent': None,
            'value': 1,
            'label': 'Number of AWCs visited',
            'frequency': 'month',
            'help_text': lady_supervisor_number_of_awcs_visited_help_text()
        }
        self.assertDictEqual(expected, data['records'][0][0])

    def test_number_of_beneficiaries_visited_data(self):
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
            'all': None,
            'format': 'number',
            'percent': None,
            'value': 2,
            'label': 'Number of Beneficiaries Visited',
            'frequency': 'month',
            'help_text': lady_supervisor_number_of_beneficiaries_visited_help_text()
        }
        self.assertDictEqual(expected, data['records'][0][1])

    def test_number_of_vhnds_observed_data(self):
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
            'all': None,
            'format': 'number',
            'percent': None,
            'value': 0,
            'label': 'Number of VHSNDs observed',
            'frequency': 'month',
            'help_text': lady_supervisor_number_of_vhnds_observed_help_text()
        }
        self.assertDictEqual(expected, data['records'][1][0])
