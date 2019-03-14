from __future__ import absolute_import

from __future__ import unicode_literals
from django.test import TestCase

from custom.icds_reports.reports.service_delivery_dashboard import get_service_delivery_data


class TestServiceDelivery(TestCase):

    def test_get_service_delivery_data(self):
        data = get_service_delivery_data(
            0,
            10,
            None,
            False,
            {
                'aggregation_level': 1,
            },
            2017,
            5,
            None,
        )
        expected = {
            'aggregationLevel': 1,
            'recordsTotal': 3,
            'recordsFiltered': 3,
            'data': [
                {
                    'gm_3_5': 234,
                    'state_name': 'st1',
                    'children_3_6': 475,
                    'children_3_5': 332,
                    'pse': '1.47 %',
                    'block_name': 'Data Not Entered',
                    'sn': '0.84 %',
                    'district_name': 'Data Not Entered',
                    'lunch_count_21_days': 4,
                    'gm': '70.48 %',
                    'supervisor_name': 'Data Not Entered',
                    'pse_attended_21_days': 7,
                    'awc_name': 'Data Not Entered'
                },
                {
                    'gm_3_5': 240,
                    'state_name': 'st2',
                    'children_3_6': 498,
                    'children_3_5': 343,
                    'pse': '12.05 %',
                    'block_name': 'Data Not Entered',
                    'sn': '2.61 %',
                    'district_name': 'Data Not Entered',
                    'lunch_count_21_days': 13,
                    'gm': '69.97 %',
                    'supervisor_name': 'Data Not Entered',
                    'pse_attended_21_days': 60,
                    'awc_name': 'Data Not Entered'
                },
                {
                    'gm_3_5': 0,
                    'state_name': 'st7',
                    'children_3_6': 1,
                    'children_3_5': 1,
                    'pse': '0.00 %',
                    'block_name': 'Data Not Entered',
                    'sn': '0.00 %',
                    'district_name': 'Data Not Entered',
                    'lunch_count_21_days': 0,
                    'gm': '0.00 %',
                    'supervisor_name': 'Data Not Entered',
                    'pse_attended_21_days': 0,
                    'awc_name': 'Data Not Entered'
                }
            ],
            'ageSDD': None,
        }
        self.assertDictEqual(expected, data)

    def test_get_service_delivery_data_state(self):
        data = get_service_delivery_data(
            0,
            10,
            'district_name',
            False,
            {
                'aggregation_level': 2,
                'state_id': 'st1',
            },
            2017,
            5,
            None,
        )
        expected = {
            'aggregationLevel': 2,
            'recordsTotal': 1,
            'recordsFiltered': 1,
            'data': [
                {
                    'gm_3_5': 234,
                    'state_name': 'st1',
                    'children_3_6': 475,
                    'children_3_5': 332,
                    'pse': '1.47 %',
                    'block_name': 'Data Not Entered',
                    'sn': '0.84 %',
                    'district_name': 'd1',
                    'lunch_count_21_days': 4,
                    'gm': '70.48 %',
                    'supervisor_name': 'Data Not Entered',
                    'pse_attended_21_days': 7,
                    'awc_name': 'Data Not Entered'
                }
            ],
            'ageSDD': None,
        }
        self.assertDictEqual(expected, data)
