from django.test import TestCase

from custom.icds_reports.reports.service_delivery_dashboard_data import get_service_delivery_details


class TestServiceDeliveryDetails(TestCase):

    def test_get_service_delivery_report_details_thr(self):
        get_service_delivery_details.clear('icds-cas', 0, 10, None, False,
                                        {'aggregation_level': 1}, 2017, 5, 'thr')
        data = get_service_delivery_details(
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
            'thr',
        )
        expected = {
            'data': [
                {
                    'state_name': 'st1',
                    'district_name': 'Data Not Entered',
                    'block_name': 'Data Not Entered',
                    'supervisor_name': 'Data Not Entered',
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 10,
                    'thr_0_days': '17.92 %',
                    'thr_1_7_days': '22.22 %',
                    'thr_8_14_days': '12.54 %',
                    'thr_15_20_days': '18.64 %',
                    'thr_21_24_days': '20.07 %',
                    'thr_25_days': '8.60 %',
                    'thr_0_days_val': 50,
                    'thr_1_7_days_val': 62,
                    'thr_8_14_days_val': 35,
                    'thr_15_20_days_val': 52,
                    'thr_21_24_days_val': 56,
                    'thr_25_days_val': 24,
                    'thr_eligible': 279
                },
                {
                    'state_name': 'st2',
                    'district_name': 'Data Not Entered',
                    'block_name': 'Data Not Entered',
                    'supervisor_name': 'Data Not Entered',
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 11,
                    'thr_0_days': '10.69 %',
                    'thr_1_7_days': '9.12 %',
                    'thr_8_14_days': '7.23 %',
                    'thr_15_20_days': '16.04 %',
                    'thr_21_24_days': '7.86 %',
                    'thr_25_days': '49.06 %',
                    'thr_0_days_val': 34,
                    'thr_1_7_days_val': 29,
                    'thr_8_14_days_val': 23,
                    'thr_15_20_days_val': 51,
                    'thr_21_24_days_val': 25,
                    'thr_25_days_val': 156,
                    'thr_eligible': 318
                },
                {
                    'state_name': 'st7',
                    'district_name': 'Data Not Entered',
                    'block_name': 'Data Not Entered',
                    'supervisor_name': 'Data Not Entered',
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 1,
                    'thr_0_days': '100.00 %',
                    'thr_1_7_days': '0.00 %',
                    'thr_8_14_days': '0.00 %',
                    'thr_15_20_days': '0.00 %',
                    'thr_21_24_days': '0.00 %',
                    'thr_25_days': '0.00 %',
                    'thr_0_days_val': 1,
                    'thr_1_7_days_val': 0,
                    'thr_8_14_days_val': 0,
                    'thr_15_20_days_val': 0,
                    'thr_21_24_days_val': 0,
                    'thr_25_days_val': 0,
                    'thr_eligible': 1
                }
            ],
            'aggregationLevel': 1,
            'recordsTotal': 3,
            'recordsFiltered': 3
        }

        self.assertDictEqual(expected, data)

    def test_get_service_delivery_report_details_cbe(self):
        get_service_delivery_details.clear('icds-cas', 0, 10, None, False,
                                        {'aggregation_level': 1}, 2017, 5, 'cbe')
        data = get_service_delivery_details(
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
            'cbe',
        )
        expected = {
            'data': [
                {
                    'state_name': 'st1',
                    'district_name': 'Data Not Entered',
                    'block_name': 'Data Not Entered',
                    'supervisor_name': 'Data Not Entered',
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 10,
                    'cbe_conducted': 1,
                    'third_fourth_month_of_pregnancy_count': 0,
                    'annaprasan_diwas_count': 0,
                    'suposhan_diwas_count': 0,
                    'coming_of_age_count': 0,
                    'public_health_message_count': 1
                },
                {
                    'state_name': 'st2',
                    'district_name': 'Data Not Entered',
                    'block_name': 'Data Not Entered',
                    'supervisor_name': 'Data Not Entered',
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 11,
                    'cbe_conducted': 2,
                    'third_fourth_month_of_pregnancy_count': 0,
                    'annaprasan_diwas_count': 1,
                    'suposhan_diwas_count': 1,
                    'coming_of_age_count': 0,
                    'public_health_message_count': 0
                },
                {
                    'state_name': 'st7',
                    'district_name': 'Data Not Entered',
                    'block_name': 'Data Not Entered',
                    'supervisor_name': 'Data Not Entered',
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 1,
                    'cbe_conducted': 0,
                    'third_fourth_month_of_pregnancy_count': 0,
                    'annaprasan_diwas_count': 0,
                    'suposhan_diwas_count': 0,
                    'coming_of_age_count': 0,
                    'public_health_message_count': 0
                }
            ],
            'aggregationLevel': 1,
            'recordsTotal': 3,
            'recordsFiltered': 3
        }
        self.assertDictEqual(expected, data)

    def test_get_service_delivery_report_details_pse(self):
        get_service_delivery_details.clear('icds-cas', 0, 10, None, False,
                                        {'aggregation_level': 1}, 2017, 5, 'pse')
        data = get_service_delivery_details(
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
            'pse',
        )
        expected = {
            'data': [
                {
                    'state_name': 'st1',
                    'district_name': 'Data Not Entered',
                    'block_name': 'Data Not Entered',
                    'supervisor_name': 'Data Not Entered',
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 10,
                    'pse_0_days': '7.87 %',
                    'pse_1_7_days': '34.78 %',
                    'pse_8_14_days': '39.54 %',
                    'pse_15_20_days': '16.36 %',
                    'pse_21_24_days': '1.45 %',
                    'pse_25_days': '0.00 %',
                    'pse_0_days_val': 38,
                    'pse_1_7_days_val': 168,
                    'pse_8_14_days_val': 191,
                    'pse_15_20_days_val': 79,
                    'pse_21_24_days_val': 7,
                    'pse_25_days_val': 0,
                    'pse_eligible': 483
                },
                {
                    'state_name': 'st2',
                    'district_name': 'Data Not Entered',
                    'block_name': 'Data Not Entered',
                    'supervisor_name': 'Data Not Entered',
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 11,
                    'pse_0_days': '8.28 %',
                    'pse_1_7_days': '38.66 %',
                    'pse_8_14_days': '32.35 %',
                    'pse_15_20_days': '9.07 %',
                    'pse_21_24_days': '7.69 %',
                    'pse_25_days': '3.94 %',
                    'pse_0_days_val': 42,
                    'pse_1_7_days_val': 196,
                    'pse_8_14_days_val': 164,
                    'pse_15_20_days_val': 46,
                    'pse_21_24_days_val': 39,
                    'pse_25_days_val': 20,
                    'pse_eligible': 507
                },
                {
                    'state_name': 'st7',
                    'district_name': 'Data Not Entered',
                    'block_name': 'Data Not Entered',
                    'supervisor_name': 'Data Not Entered',
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 1,
                    'pse_0_days': '100.00 %',
                    'pse_1_7_days': '0.00 %',
                    'pse_8_14_days': '0.00 %',
                    'pse_15_20_days': '0.00 %',
                    'pse_21_24_days': '0.00 %',
                    'pse_25_days': '0.00 %',
                    'pse_0_days_val': 1,
                    'pse_1_7_days_val': 0,
                    'pse_8_14_days_val': 0,
                    'pse_15_20_days_val': 0,
                    'pse_21_24_days_val': 0,
                    'pse_25_days_val': 0,
                    'pse_eligible': 1
                }
            ],
            'aggregationLevel': 1,
            'recordsTotal': 3,
            'recordsFiltered': 3
        }
        self.assertDictEqual(expected, data)

    def test_get_service_delivery_report_details_sn(self):
        get_service_delivery_details.clear('icds-cas', 0, 10, None, False,
                                        {'aggregation_level': 1}, 2017, 5, 'sn')
        data = get_service_delivery_details(
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
            'sn',
        )
        expected = {
            'data': [
                {
                    'state_name': 'st1',
                    'district_name': 'Data Not Entered',
                    'block_name': 'Data Not Entered',
                    'supervisor_name': 'Data Not Entered',
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 10,
                    'lunch_0_days': '98.76 %',
                    'lunch_1_7_days': '0.21 %',
                    'lunch_8_14_days': '0.21 %',
                    'lunch_15_20_days': '0.00 %',
                    'lunch_21_24_days': '0.83 %',
                    'lunch_25_days': '0.00 %',
                    'lunch_0_days_val': 477,
                    'lunch_1_7_days_val': 1,
                    'lunch_8_14_days_val': 1,
                    'lunch_15_20_days_val': 0,
                    'lunch_21_24_days_val': 4,
                    'lunch_25_days_val': 0,
                    'pse_eligible': 483
                },
                {
                    'state_name': 'st2',
                    'district_name': 'Data Not Entered',
                    'block_name': 'Data Not Entered',
                    'supervisor_name': 'Data Not Entered',
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 11,
                    'lunch_0_days': '97.44 %',
                    'lunch_1_7_days': '0.00 %',
                    'lunch_8_14_days': '0.00 %',
                    'lunch_15_20_days': '0.39 %',
                    'lunch_21_24_days': '2.17 %',
                    'lunch_25_days': '0.00 %',
                    'lunch_0_days_val': 494,
                    'lunch_1_7_days_val': 0,
                    'lunch_8_14_days_val': 0,
                    'lunch_15_20_days_val': 2,
                    'lunch_21_24_days_val': 11,
                    'lunch_25_days_val': 0,
                    'pse_eligible': 507
                },
                {
                    'state_name': 'st7',
                    'district_name': 'Data Not Entered',
                    'block_name': 'Data Not Entered',
                    'supervisor_name': 'Data Not Entered',
                    'awc_name': 'Data Not Entered',
                    'num_launched_awcs': 1,
                    'lunch_0_days': '100.00 %',
                    'lunch_1_7_days': '0.00 %',
                    'lunch_8_14_days': '0.00 %',
                    'lunch_15_20_days': '0.00 %',
                    'lunch_21_24_days': '0.00 %',
                    'lunch_25_days': '0.00 %',
                    'lunch_0_days_val': 1,
                    'lunch_1_7_days_val': 0,
                    'lunch_8_14_days_val': 0,
                    'lunch_15_20_days_val': 0,
                    'lunch_21_24_days_val': 0,
                    'lunch_25_days_val': 0,
                    'pse_eligible': 1
                }
            ],
            'aggregationLevel': 1,
            'recordsTotal': 3,
            'recordsFiltered': 3
        }
        self.assertDictEqual(expected, data)
