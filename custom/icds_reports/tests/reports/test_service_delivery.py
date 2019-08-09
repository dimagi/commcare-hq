from __future__ import absolute_import

from __future__ import unicode_literals
from django.test import TestCase

from custom.icds_reports.reports.service_delivery_dashboard import get_service_delivery_data


class TestServiceDelivery(TestCase):

    def test_get_service_delivery_data_0_3(self):
        data = get_service_delivery_data(
            'icds-cas',
            0,
            10,
            None,
            False,
            {
                'aggregation_level': 1,
            },
            2017,
            5,
            'pw_lw_children',
        )
        expected = {
            'aggregationLevel': 1,
            'recordsTotal': 3,
            'recordsFiltered': 3,
            'data': [
                {
                    'state_name': 'st1',
                    'num_awcs_conducted_vhnd': 2,
                    'gm': '58.04 %',
                    'supervisor_name': 'Data Not Entered',
                    'total_thr_candidates': 279,
                    'awc_name': 'Data Not Entered',
                    'num_awcs_conducted_cbe': 1,
                    'thr_given_21_days': 80,
                    'valid_visits': 3,
                    'expected_visits': 304,
                    'thr': '28.67 %',
                    'num_launched_awcs': 9,
                    'block_name': 'Data Not Entered',
                    'children_0_3': 143,
                    'gm_0_3': 83,
                    'district_name': 'Data Not Entered',
                    'home_visits': '0.99 %'
                },
                {
                    'state_name': 'st2',
                    'num_awcs_conducted_vhnd': 6,
                    'gm': '81.29 %',
                    'supervisor_name': 'Data Not Entered',
                    'total_thr_candidates': 318,
                    'awc_name': 'Data Not Entered',
                    'num_awcs_conducted_cbe': 1,
                    'thr_given_21_days': 181,
                    'valid_visits': 0,
                    'expected_visits': 333,
                    'thr': '56.92 %',
                    'num_launched_awcs': 11,
                    'block_name': 'Data Not Entered',
                    'children_0_3': 171,
                    'gm_0_3': 139,
                    'district_name': 'Data Not Entered',
                    'home_visits': '0.00 %'
                },
                {
                    'state_name': 'st7',
                    'num_awcs_conducted_vhnd': 0,
                    'gm': 'Data Not Entered',
                    'supervisor_name': 'Data Not Entered',
                    'total_thr_candidates': 1,
                    'awc_name': 'Data Not Entered',
                    'num_awcs_conducted_cbe': 0,
                    'thr_given_21_days': 0,
                    'valid_visits': 0,
                    'expected_visits': 1,
                    'thr': '0.00 %',
                    'num_launched_awcs': 1,
                    'block_name': 'Data Not Entered',
                    'children_0_3': 0,
                    'gm_0_3': 0,
                    'district_name': 'Data Not Entered',
                    'home_visits': '0.00 %'
                }
            ],
        }
        self.assertDictEqual(expected, data)

    def test_get_service_delivery_data_state_0_3(self):
        data = get_service_delivery_data(
            'icds-cas',
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
            'pw_lw_children',
        )
        expected = {
            'aggregationLevel': 2,
            'recordsTotal': 1,
            'recordsFiltered': 1,
            'data': [
                {
                    'state_name': 'st1',
                    'num_awcs_conducted_vhnd': 2,
                    'gm': '58.04 %',
                    'supervisor_name': 'Data Not Entered',
                    'total_thr_candidates': 279,
                    'awc_name': 'Data Not Entered',
                    'num_awcs_conducted_cbe': 1,
                    'thr_given_21_days': 80,
                    'valid_visits': 3,
                    'expected_visits': 304,
                    'thr': '28.67 %',
                    'num_launched_awcs': 9,
                    'block_name': 'Data Not Entered',
                    'children_0_3': 143,
                    'gm_0_3': 83,
                    'district_name': 'd1',
                    'home_visits': '0.99 %'
                }
            ],
        }
        self.assertDictEqual(expected, data)

    def test_get_service_delivery_data_3_6(self):
        data = get_service_delivery_data(
            'icds-cas',
            0,
            10,
            None,
            False,
            {
                'aggregation_level': 1,
            },
            2017,
            5,
            'children',
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
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 9
                },
                {
                    'gm_3_5': 240,
                    'state_name': 'st2',
                    'children_3_6': 498,
                    'children_3_5': 343,
                    'pse': '12.05 %',
                    'block_name': 'Data Not Entered',
                    'sn': '2.41 %',
                    'district_name': 'Data Not Entered',
                    'lunch_count_21_days': 12,
                    'gm': '69.97 %',
                    'supervisor_name': 'Data Not Entered',
                    'pse_attended_21_days': 60,
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 11
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
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 1,
                }
            ],
        }
        self.assertDictEqual(expected, data)

    def test_get_service_delivery_data_state_3_6(self):
        data = get_service_delivery_data(
            'icds-cas',
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
            'children',
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
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 9
                }
            ],
        }
        self.assertDictEqual(expected, data)
