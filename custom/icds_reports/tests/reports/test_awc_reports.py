# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import json
import datetime

from datetime import date
from django.core.serializers.json import DjangoJSONEncoder
from django.test import TestCase
from mock import mock

from custom.icds_reports.reports.awc_reports import get_beneficiary_details, get_awc_reports_system_usage, \
    get_awc_reports_pse, get_awc_reports_maternal_child, get_awc_report_demographics, \
    get_awc_report_beneficiary, get_awc_report_pregnant, get_pregnant_details, get_awc_report_lactating
from custom.icds_reports.messages import new_born_with_low_weight_help_text, wasting_help_text, \
    exclusive_breastfeeding_help_text, early_initiation_breastfeeding_help_text, \
    children_initiated_appropriate_complementary_feeding_help_text, institutional_deliveries_help_text, \
    percent_aadhaar_seeded_beneficiaries_help_text, percent_children_enrolled_help_text, \
    percent_pregnant_women_enrolled_help_text, percent_lactating_women_enrolled_help_text, \
    percent_adolescent_girls_enrolled_help_text
from six.moves import filter


class FirstDayOfMay(datetime.datetime):
    @classmethod
    def utcnow(cls):
        return datetime.datetime(2017, 5, 1)


class FirstDayOfMayDate(date):
    @classmethod
    def today(cls):
        return date(2017, 5, 1)


class SecondDayOfMay(date):
    @classmethod
    def utcnow(cls):
        return datetime.datetime(2017, 5, 2)


class TestAWCReport(TestCase):
    def test_beneficiary_details_recorded_weight_none(self):
        data = get_beneficiary_details(
            case_id='6b234c5b-883c-4849-9dfd-b1571af8717b',
            awc_id='a50',
            selected_month=(2017, 6, 1)
        )
        self.assertEqual(data['age_in_months'], 69)
        self.assertEqual(data['sex'], 'M')
        self.assertEqual(data['person_name'], 'Name 3342')
        self.assertEqual(data['mother_name'], 'संगीता')

    def test_beneficiary_details_recorded_weight_is_not_none(self):
        data = get_beneficiary_details(
            case_id='8e226cc6-740f-4146-b017-69d9f6e9651b',
            awc_id='a21',
            selected_month=(2017, 6, 1)
        )
        self.assertEqual(data['age_in_months'], 54)
        self.assertEqual(data['sex'], 'M')
        self.assertEqual(data['person_name'], 'Name 3141')
        self.assertEqual(data['mother_name'], 'शियामु बाई')
        self.assertEqual(next(filter(lambda r: r['x'] == 53, data['weight']))['y'], 12.6)
        self.assertEqual(next(filter(lambda r: r['x'] == 53, data['height']))['y'], 96.0)
        self.assertEqual(next(filter(lambda r: r['x'] == 96.0, data['wfl']))['y'], 12.6)

    def test_beneficiary_details_have_age_in_month_not_have_recorded_height(self):
        data = get_beneficiary_details(
            case_id='411c4234-8475-415a-9c28-911b85868aa5',
            awc_id='a15',
            selected_month=(2017, 6, 1)
        )
        self.assertEqual(data['age_in_months'], 37)
        self.assertEqual(data['sex'], 'F')
        self.assertEqual(data['person_name'], 'Name 3483')
        self.assertEqual(data['mother_name'], 'रींकीकुँवर')

    def test_awc_reports_system_usage_AWC_days_open(self):
        self.assertDictEqual(
            get_awc_reports_system_usage(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 1),
                (2017, 4, 1),
                (2017, 3, 1),
                'aggregation_level'
            )['kpi'][0][0],
            {
                "all": "",
                "format": "number",
                "percent": 100.0,
                "value": 18,
                "label": "AWC Days Open",
                "frequency": "month",
                "help_text": "The total number of days the AWC is open in the given month. "
                             "The AWC is expected to be open 6 days a week"
                             " (Not on Sundays and public holidays)"
            }
        )

    def test_awc_reports_system_usage_percentage_of_eligible_children_ICDS_beneficiaries_between_0_6_years(self):
        self.assertDictEqual(
            get_awc_reports_system_usage(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 1),
                (2017, 4, 1),
                (2017, 3, 1),
                'aggregation_level'
            )['kpi'][0][1],
            {
                "all": 0,
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Percentage of eligible children (ICDS beneficiaries between 0-6 years)"
                         " who have been weighed in the current month",
                "frequency": "month",
                "help_text": "Percentage of AWCs with a functional toilet"
            }
        )

    def test_awc_reports_system_usage_kpi_length(self):
        self.assertEqual(
            len(get_awc_reports_system_usage(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 1),
                (2017, 4, 1),
                (2017, 3, 1),
                'aggregation_level'
            )['kpi']),
            1
        )

    def test_awc_reports_system_usage_kpi_total_length(self):
        data = get_awc_reports_system_usage(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 1),
                (2017, 4, 1),
                (2017, 3, 1),
                'aggregation_level'
            )['kpi']

        self.assertEqual(
            sum([len(record_row) for record_row in data]),
            2
        )

    def test_awc_reports_system_usage_AWC_days_open_per_week_chart(self):
        self.assertEqual(
            get_awc_reports_system_usage(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 1),
                (2017, 4, 1),
                (2017, 3, 1),
                'aggregation_level'
            )['charts'][0],
            [
                {
                    "classed": "dashed",
                    "values": [
                        [
                            1491523200000,
                            1
                        ],
                        [
                            1491609600000,
                            1
                        ],
                        [
                            1491782400000,
                            1
                        ],
                        [
                            1491955200000,
                            1
                        ],
                        [
                            1492473600000,
                            1
                        ],
                        [
                            1492732800000,
                            1
                        ],
                        [
                            1492992000000,
                            1
                        ],
                        [
                            1493078400000,
                            1
                        ],
                        [
                            1493251200000,
                            1
                        ]
                    ],
                    "key": "AWC Days Open Per Week"
                }
            ]
        )

    def test_awc_reports_system_usage_PSE_average_weekly_attendance(self):
        self.assertEqual(
            get_awc_reports_system_usage(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 1),
                (2017, 4, 1),
                (2017, 3, 1),
                'aggregation_level'
            )['charts'][1],
            [
                {
                    "classed": "dashed",
                    "values": [
                        [
                            1491523200000,
                            0.65625
                        ],
                        [
                            1491609600000,
                            0.64516129
                        ],
                        [
                            1491782400000,
                            0.677419355
                        ],
                        [
                            1491955200000,
                            0.612903226
                        ],
                        [
                            1492473600000,
                            0.612903226
                        ],
                        [
                            1492732800000,
                            0.64516129
                        ],
                        [
                            1492992000000,
                            0.64516129
                        ],
                        [
                            1493078400000,
                            0.64516129
                        ],
                        [
                            1493251200000,
                            0.64516129
                        ]
                    ],
                    "key": "PSE- Average Weekly Attendance"
                }
            ]
        )

    def test_awc_reports_system_usage_length(self):
        self.assertEqual(
            len(get_awc_reports_system_usage(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 1),
                (2017, 4, 1),
                (2017, 3, 1),
                'aggregation_level'
            )['charts']),
            2
        )

    def test_awc_reports_system_usage_keys(self):
        self.assertEqual(
            list(get_awc_reports_system_usage(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 1),
                (2017, 4, 1),
                (2017, 3, 1),
                'aggregation_level'
            ).keys()),
            ['kpi', 'charts']
        )

    def test_awc_reports_pse_images_0(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            data['images'][0],
            [
                {
                    "date": "01/05/2017",
                    "image": None,
                    "id": 0
                },
                {
                    "date": "02/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "00a368e6-e88f-41ee-96aa-25a8ec5ab3d6/1493703284010.jpg",
                    "id": 1
                },
                {
                    "date": "03/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "ef336dda-12a1-42a4-9bee-405d17c2aba8/1493790538044.jpg",
                    "id": 2
                },
                {
                    "date": "04/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "00ec149e-c1a9-4083-a73c-cdc39df17137/1493876634200.jpg",
                    "id": 3
                }
            ]
        )

    def test_awc_reports_pse_images_1(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            data['images'][1],
            [
                {
                    "date": "05/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "ebb1f3c8-34c7-4ed1-9f35-0b209cb4d683/1493959451474.jpg",
                    "id": 4
                },
                {
                    "date": "06/05/2017",
                    "image": None,
                    "id": 5
                },
                {
                    "date": "07/05/2017",
                    "image": None,
                    "id": 6
                },
                {
                    "date": "08/05/2017",
                    "image": None,
                    "id": 7
                }
            ]
        )

    def test_awc_reports_pse_images_2(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            data['images'][2],
            [
                {
                    "date": "09/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "eb20b019-97ef-45e0-9698-fda3d964a096/1494308187855.jpg",
                    "id": 8
                },
                {
                    "date": "10/05/2017",
                    "image": None,
                    "id": 9
                },
                {
                    "date": "11/05/2017",
                    "image": None,
                    "id": 10
                },
                {
                    "date": "12/05/2017",
                    "image": None,
                    "id": 11
                }
            ]
        )

    def test_awc_reports_pse_images_3(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            data['images'][3],
            [
                {
                    "date": "13/05/2017",
                    "image": None,
                    "id": 12
                },
                {
                    "date": "14/05/2017",
                    "image": None,
                    "id": 13
                },
                {
                    "date": "15/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "036ab123-0a1e-43b6-8e7d-4bcf9abcdfa2/1494826363729.jpg",
                    "id": 14
                },
                {
                    "date": "16/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "dda9c427-4ba7-4f90-9c5b-d2a02cff9e31/1494911839185.jpg",
                    "id": 15
                }
            ]
        )

    def test_awc_reports_pse_images_4(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            data['images'][4],
            [
                {
                    "date": "17/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "1be8a49b-c63c-4288-bcb2-9e5bf132834f/1494997946602.jpg",
                    "id": 16
                },
                {
                    "date": "18/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "c7f6d174-1218-4f8e-ab84-f80e17b1ebdb/1495084707730.jpg",
                    "id": 17
                },
                {
                    "date": "19/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "416990d9-f354-457f-8c52-1866e98840f5/1495173038810.jpg",
                    "id": 18
                },
                {
                    "date": "20/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "3fea99f8-c6f4-48c9-9386-152639fe1b17/1495259635314.jpg",
                    "id": 19
                }
            ]
        )

    def test_awc_reports_pse_images_5(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            data['images'][5],
            [
                {
                    "date": "21/05/2017",
                    "image": None,
                    "id": 20
                },
                {
                    "date": "22/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "ce528857-f34e-4785-913f-41d221fbeed8/1495432106324.jpg",
                    "id": 21
                },
                {
                    "date": "23/05/2017",
                    "image": None,
                    "id": 22
                },
                {
                    "date": "24/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "5d0f2aa4-6d5b-424f-91d1-c4afb2d0555b/1495605536823.jpg",
                    "id": 23
                }
            ]
        )

    def test_awc_reports_pse_images_6(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            data['images'][6],
            [
                {
                    "date": "25/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "20e4d641-a85a-4927-96ab-994fa46a8ea0/1495690578649.jpg",
                    "id": 24
                },
                {
                    "date": "26/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "f86e701b-1531-469f-8996-705e297bf498/1495776461721.jpg",
                    "id": 25
                },
                {
                    "date": "27/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "6701b39d-4b6f-4ae3-8a88-eadb61b1a105/1495865744995.jpg",
                    "id": 26
                },
                {
                    "date": "28/05/2017",
                    "image": None,
                    "id": 27
                }
            ]
        )

    def test_awc_reports_pse_images_7(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            data['images'][7],
            [
                {
                    "date": "29/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "6376d77d-bb2a-48ac-9042-7892dda97bba/1496036503892.jpg",
                    "id": 28
                },
                {
                    "date": "30/05/2017",
                    "image": "http://localhost:8000/a/icds-cas/icds_dashboard/icds_image_accessor/"
                             "c0d002ca-f7b0-4bd2-a531-881b46610c2f/1496120210768.jpg",
                    "id": 29
                },
                {
                    "date": "31/05/2017",
                    "image": None,
                    "id": 30
                }
            ]
        )

    def test_awc_reports_pse_images_length(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            len(data['images']),
            8
        )

    def test_awc_reports_pse_kpi(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            data['kpi'],
            [
                [
                    {
                        "color": "green",
                        "all": "",
                        "frequency": "month",
                        "format": "number",
                        "percent": 100.0,
                        "value": 18,
                        "label": "AWC Days Open"
                    }
                ]
            ]
        )

    def test_awc_reports_pse_charts_0(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            data['charts'][0],
            [
                {
                    "color": "#006fdf",
                    "classed": "dashed",
                    "strokeWidth": 2,
                    "values": [
                        {
                            "y": 4,
                            "x": 1493596800000
                        },
                        {
                            "y": 1,
                            "x": 1494201600000
                        },
                        {
                            "y": 6,
                            "x": 1494806400000
                        },
                        {
                            "y": 5,
                            "x": 1495411200000
                        },
                        {
                            "y": 2,
                            "x": 1496016000000
                        }
                    ],
                    "key": "AWC Days Open per week"
                }
            ]
        )

    def test_awc_reports_pse_charts_1(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            data['charts'][1],
            [
                {
                    "color": "#006fdf",
                    "classed": "dashed",
                    "strokeWidth": 2,
                    "values": [
                        {
                            "y": 0,
                            "x": 1493596800000,
                            "attended": 0,
                            "eligible": 0
                        },
                        {
                            "y": 0.741935484,
                            "x": 1493683200000,
                            "attended": 23,
                            "eligible": 31
                        },
                        {
                            "y": 0.806451613,
                            "x": 1493769600000,
                            "attended": 25,
                            "eligible": 31
                        },
                        {
                            "y": 0.8,
                            "x": 1493856000000,
                            "attended": 24,
                            "eligible": 30
                        },
                        {
                            "y": 0.8,
                            "x": 1493942400000,
                            "attended": 24,
                            "eligible": 30
                        },
                        {
                            "y": 0,
                            "x": 1494028800000,
                            "attended": 0,
                            "eligible": 0
                        },
                        {
                            "y": 0,
                            "x": 1494115200000,
                            "attended": 0,
                            "eligible": 0
                        },
                        {
                            "y": 0,
                            "x": 1494201600000,
                            "attended": 0,
                            "eligible": 0
                        },
                        {
                            "y": 0.8,
                            "x": 1494288000000,
                            "attended": 24,
                            "eligible": 30
                        },
                        {
                            "y": 0,
                            "x": 1494374400000,
                            "attended": 0,
                            "eligible": 0
                        },
                        {
                            "y": 0,
                            "x": 1494460800000,
                            "attended": 0,
                            "eligible": 0
                        },
                        {
                            "y": 0,
                            "x": 1494547200000,
                            "attended": 0,
                            "eligible": 0
                        },
                        {
                            "y": 0,
                            "x": 1494633600000,
                            "attended": 0,
                            "eligible": 0
                        },
                        {
                            "y": 0,
                            "x": 1494720000000,
                            "attended": 0,
                            "eligible": 0
                        },
                        {
                            "y": 1.0,
                            "x": 1494806400000,
                            "attended": 30,
                            "eligible": 30
                        },
                        {
                            "y": 0.666666667,
                            "x": 1494892800000,
                            "attended": 20,
                            "eligible": 30
                        },
                        {
                            "y": 0.733333333,
                            "x": 1494979200000,
                            "attended": 22,
                            "eligible": 30
                        },
                        {
                            "y": 0.766666667,
                            "x": 1495065600000,
                            "attended": 23,
                            "eligible": 30
                        },
                        {
                            "y": 0.666666667,
                            "x": 1495152000000,
                            "attended": 20,
                            "eligible": 30
                        },
                        {
                            "y": 0.633333333,
                            "x": 1495238400000,
                            "attended": 19,
                            "eligible": 30
                        },
                        {
                            "y": 0,
                            "x": 1495324800000,
                            "attended": 0,
                            "eligible": 0
                        },
                        {
                            "y": 0.666666667,
                            "x": 1495411200000,
                            "attended": 20,
                            "eligible": 30
                        },
                        {
                            "y": 0,
                            "x": 1495497600000,
                            "attended": 0,
                            "eligible": 0
                        },
                        {
                            "y": 0.666666667,
                            "x": 1495584000000,
                            "attended": 20,
                            "eligible": 30
                        },
                        {
                            "y": 0.666666667,
                            "x": 1495670400000,
                            "attended": 20,
                            "eligible": 30
                        },
                        {
                            "y": 0.666666667,
                            "x": 1495756800000,
                            "attended": 20,
                            "eligible": 30
                        },
                        {
                            "y": 0.666666667,
                            "x": 1495843200000,
                            "attended": 20,
                            "eligible": 30
                        },
                        {
                            "y": 0,
                            "x": 1495929600000,
                            "attended": 0,
                            "eligible": 0
                        },
                        {
                            "y": 0.655172414,
                            "x": 1496016000000,
                            "attended": 19,
                            "eligible": 29
                        },
                        {
                            "y": 1.0,
                            "x": 1496102400000,
                            "attended": 29,
                            "eligible": 29
                        },
                        {
                            "y": 0,
                            "x": 1496188800000,
                            "attended": 0,
                            "eligible": 0
                        }
                    ],
                    "key": "PSE - Daily Attendance"
                }
            ]
        )

    def test_awc_reports_pse_charts_length(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            len(data['charts']),
            2
        )

    def test_awc_reports_pse_map(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertDictEqual(
            data['map'],
            {
                "markers": {}
            }
        )

    def test_awc_reports_pse_keys(self):
        data = get_awc_reports_pse(
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            'icds-cas'
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertItemsEqual(
            data,
            ["images", "kpi", "charts", "map"]
        )

    def test_awc_reports_maternal_child_underweight_weight_for_age(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
        )
        self.assertDictEqual(
            data['kpi'][0][0],
            {
                "color": "red",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Underweight (Weight-for-Age)",
                "help_text": (
                    "Of the total children weighed, the percentage of children between 0-5 years who were "
                    "moderately/severely underweight in the current month. Children who are moderately or "
                    "severely underweight have a higher risk of mortality. "
                )
            }
        )

    def test_awc_reports_maternal_child_wasting_weight_for_height(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
        )
        self.assertDictEqual(
            data['kpi'][0][1],
            {
                "color": "red",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Wasting (Weight-for-Height)",
                "help_text": wasting_help_text("0 - 5 years")
            }
        )

    def test_awc_reports_maternal_child_stunting_height_for_age(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
        )
        self.assertDictEqual(
            data['kpi'][1][0],
            {
                "color": "red",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Stunting (Height-for-Age)",
                "help_text": (
                    "Of the children whose height was measured, the percentage of children between "
                    "0 - 5 years who were moderately/severely stunted in the current month."
                    "<br/><br/>"
                    "Stunting is a sign of chronic undernutrition and has long lasting harmful consequences "
                    "on the growth of a child"
                )
            }
        )

    def test_awc_reports_maternal_child_wasting_weight_for_height_icds_features_flag(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
            icds_feature_flag=True
        )
        self.assertDictEqual(
            data['kpi'][0][1],
            {
                "color": "red",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Wasting (Weight-for-Height)",
                "help_text": wasting_help_text("0 - 5 years")
            }
        )

    def test_awc_reports_maternal_child_stunting_height_for_age_icds_features_flag(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
            icds_feature_flag=True
        )
        self.assertDictEqual(
            data['kpi'][1][0],
            {
                "color": "red",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Stunting (Height-for-Age)",
                "help_text": (
                    "Of the children whose height was measured, the percentage of children between "
                    "0 - 5 years who were moderately/severely stunted in the current month."
                    "<br/><br/>"
                    "Stunting is a sign of chronic undernutrition and has long lasting harmful consequences "
                    "on the growth of a child"
                )
            }
        )

    def test_awc_reports_maternal_child_weighing_efficiency(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
        )
        self.assertDictEqual(
            data['kpi'][1][1],
            {
                "color": "green",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Weighing Efficiency",
                'help_text': "Of the children between the ages of 0-5 years who are enrolled for Anganwadi "
                             "Services, the percentage who were weighed in the given month. ",
            }
        )

    def test_awc_reports_maternal_child_newborns_with_low_birth_weight(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
        )
        self.assertDictEqual(
            data['kpi'][2][0],
            {
                "color": "red",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Newborns with Low Birth Weight",
                'help_text': (
                    new_born_with_low_weight_help_text(html=False)
                ),
            }
        )

    def test_awc_reports_maternal_child_early_initiation_of_breastfeeding(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
        )
        self.assertDictEqual(
            data['kpi'][2][1],
            {
                "color": "green",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Early Initiation of Breastfeeding",
                'help_text': early_initiation_breastfeeding_help_text(),
            }
        )

    def test_awc_reports_maternal_child_exclusive_breastfeeding(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
        )
        self.assertDictEqual(
            data['kpi'][3][0],
            {
                "color": "green",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Exclusive breastfeeding",
                'help_text': exclusive_breastfeeding_help_text(),
            }
        )

    def test_awc_reports_maternal_child_children_initiated_appropriate_complementary_feeding(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
        )
        self.assertDictEqual(
            data['kpi'][3][1],
            {
                "color": "green",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Children initiated appropriate Complementary Feeding",
                'help_text': children_initiated_appropriate_complementary_feeding_help_text(),
            }
        )

    def test_awc_reports_maternal_child_immunization_coverage_at_age_1_year(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
        )
        self.assertDictEqual(
            data['kpi'][4][0],
            {
                "color": "green",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Immunization Coverage (at age 1 year)",
                'help_text': (
                    "Of the total number of children enrolled for Anganwadi Services who are over a year old, "
                    "the percentage of children who have received the complete immunization as per the National "
                    "Immunization Schedule of India that is required by age 1."
                    "<br/><br/>"
                    " This includes the following immunizations:<br/>"
                    " If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/>"
                    " If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1"
                ),
            }
        )

    def test_awc_reports_maternal_child_institutional_deliveries(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
        )
        self.assertDictEqual(
            data['kpi'][4][1],
            {
                "color": "green",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Institutional Deliveries",
                'help_text': institutional_deliveries_help_text(),
            }
        )

    def test_awc_reports_maternal_child_kpi_length(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            len(data['kpi']),
            5
        )

    def test_awc_reports_maternal_child_kpi_total_length(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
        )['kpi']

        self.assertEqual(
            sum([len(record_row) for record_row in data]),
            10
        )

    def test_awc_reports_maternal_child_keys(self):
        data = get_awc_reports_maternal_child(
            'icds-cas',
            {
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'awc_id': 'a1',
                'aggregation_level': 5
            },
            (2017, 5, 1),
            (2017, 4, 1),
        )
        for kpi in data['kpi']:
            for el in kpi:
                del el['help_text']
        self.assertEqual(
            list(data.keys()),
            ['kpi']
        )

    def test_awc_reports_demographics_monthly_registered_households(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 6, 1),
                (2017, 5, 1),
            )['kpi'][0][0],
            {
                "all": "",
                "format": "number",
                "color": "red",
                "percent": 0,
                "value": 139,
                "label": "Registered Households",
                "frequency": "month",
                "help_text": "Total number of households registered"
            }
        )

    def test_awc_reports_demographics_monthly_percent_aadhaar_seeded_beneficiaries(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 6, 1),
                (2017, 5, 1),
            )['kpi'][0][1],
            {
                "all": 5,
                'color': 'red',
                "format": "percent_and_div",
                "percent": -39.99999999999999,
                "value": 1,
                "label": "Percent Aadhaar-seeded Beneficiaries",
                "frequency": "month",
                "help_text": percent_aadhaar_seeded_beneficiaries_help_text()
            }
        )

    def test_awc_reports_demographics_monthly_percent_children_0_6_years_enrolled_for_anganwadi_services(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 6, 1),
                (2017, 5, 1),
            )['kpi'][1][0],
            {
                "all": 0,
                "format": "percent_and_div",
                "color": "green",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Percent children (0-6 years) enrolled for Anganwadi Services",
                "frequency": "month",
                "help_text": percent_children_enrolled_help_text()
            }
        )

    def test_awc_reports_demographics_monthly_percent_pregnant_women_enrolled_for_anganwadi_services(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 6, 1),
                (2017, 5, 1),
            )['kpi'][1][1],
            {
                "all": 2,
                "format": "percent_and_div",
                "color": "red",
                "percent": 0,
                "value": 2,
                "label": "Percent pregnant women enrolled for Anganwadi Services",
                "frequency": "month",
                "help_text": percent_pregnant_women_enrolled_help_text()
            }
        )

    def test_awc_reports_demographics_monthly_percent_lactating_women_enrolled_for_anganwadi_services(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 6, 1),
                (2017, 5, 1),
            )['kpi'][2][0],
            {
                "all": 3,
                "format": "percent_and_div",
                "color": "red",
                "percent": 0,
                "value": 3,
                "label": "Percent lactating women enrolled for Anganwadi Services",
                "frequency": "month",
                "help_text": percent_lactating_women_enrolled_help_text()
            }
        )

    def test_awc_reports_demographics_monthly_percent_adolescent_girls_11_14_years_enrolled_for_services(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 6, 1),
                (2017, 5, 1),
            )['kpi'][2][1],
            {
                "all": 0,
                "format": "percent_and_div",
                "color": "red",
                "percent": -100.0,
                "value": 0,
                "label": "Percent adolescent girls (11-14 years) enrolled for Anganwadi Services",
                "frequency": "month",
                "help_text": percent_adolescent_girls_enrolled_help_text()
            }
        )

    def test_awc_reports_demographics_monthly_kpi_length(self):
        self.assertEqual(
            len(get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 6, 1),
                (2017, 5, 1),
            )['kpi']),
            3
        )

    def test_awc_reports_demographics_monthly_kpi_total_length(self):
        data = get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 6, 1),
                (2017, 5, 1),
            )['kpi']

        self.assertEqual(
            sum([len(record_row) for record_row in data]),
            6
        )

    def test_awc_reports_demographics_monthly_chart(self):
        self.assertEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 6, 1),
                (2017, 5, 1),
            )['chart'],
            [
                {
                    "values": [
                        [
                            "0-1 month",
                            0
                        ],
                        [
                            "1-6 months",
                            0
                        ],
                        [
                            "6-12 months",
                            0
                        ],
                        [
                            "1-3 years",
                            0
                        ],
                        [
                            "3-6 years",
                            0
                        ]
                    ],
                    "classed": "dashed",
                    "key": "Children (0-6 years)"
                }
            ]
        )

    def test_awc_reports_demographics_monthly_keys(self):
        self.assertItemsEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 6, 1),
                (2017, 5, 1),
            ),
            ['kpi', 'chart']
        )

    def test_awc_reports_demographics_daily_registered_households(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 29),
                (2017, 5, 1),
            )['kpi'][0][0],
            {
                "all": "",
                "format": "number",
                "color": "green",
                "percent": "Data in the previous reporting period was 0",
                "value": 139,
                "label": "Registered Households",
                "frequency": "day",
                "help_text": "Total number of households registered"
            }
        )

    def test_awc_reports_demographics_daily_percent_aadhaar_seeded_beneficiaries(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 29),
                (2017, 5, 1),
            )['kpi'][0][1],
            {
                "all": 5,
                'color': 'green',
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 1,
                "label": "Percent Aadhaar-seeded Beneficiaries",
                "frequency": "day",
                "help_text": (
                    "Of the total number of ICDS beneficiaries, the percentage whose Adhaar identification "
                    "has been captured. "
                )
            }
        )

    def test_awc_reports_demographics_daily_percent_children_0_6_years_enrolled_for_anganwadi_services(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 29),
                (2017, 5, 1),
            )['kpi'][1][0],
            {
                "all": 0,
                "format": "percent_and_div",
                "color": "green",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Percent children (0-6 years) enrolled for Anganwadi Services",
                "frequency": "day",
                "help_text": percent_children_enrolled_help_text()
            }
        )

    def test_awc_reports_demographics_daily_percent_pregnant_women_enrolled_for_anganwadi_services(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 29),
                (2017, 5, 1),
            )['kpi'][1][1],
            {
                "all": 2,
                "format": "percent_and_div",
                "color": "green",
                "percent": "Data in the previous reporting period was 0",
                "value": 2,
                "label": "Percent pregnant women enrolled for Anganwadi Services",
                "frequency": "day",
                "help_text": percent_pregnant_women_enrolled_help_text()
            }
        )

    def test_awc_reports_demographics_daily_percent_lactating_women_enrolled_for_anganwadi_services(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 29),
                (2017, 5, 1),
            )['kpi'][2][0],
            {
                "all": 3,
                "format": "percent_and_div",
                "color": "green",
                "percent": "Data in the previous reporting period was 0",
                "value": 3,
                "label": "Percent lactating women enrolled for Anganwadi Services",
                "frequency": "day",
                "help_text": percent_lactating_women_enrolled_help_text()
            }
        )

    def test_awc_reports_demographics_daily_percent_adolescent_girls_11_14_years_enrolled_for_services(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 29),
                (2017, 5, 1),
            )['kpi'][2][1],
            {
                "all": 0,
                "format": "percent_and_div",
                "color": "green",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": (
                    "Percent adolescent girls (11-14 years) enrolled for Anganwadi Services"
                ),
                "frequency": "day",
                "help_text": percent_adolescent_girls_enrolled_help_text()
            }
        )

    def test_awc_reports_demographics_daily_kpi_length(self):
        self.assertEqual(
            len(get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 29),
                (2017, 5, 1),
            )['kpi']),
            3
        )

    def test_awc_reports_demographics_daily_kpi_total_length(self):
        data = get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 29),
                (2017, 5, 1),
            )['kpi']

        self.assertEqual(
            sum([len(record_row) for record_row in data]),
            6
        )

    def test_awc_reports_demographics_daily_chart(self):
        self.assertEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 29),
                (2017, 5, 1),
            )['chart'],
            [{
                "values": [
                    ["0-1 month", 0],
                    ["1-6 months", 0],
                    ["6-12 months", 0],
                    ["1-3 years", 0],
                    ["3-6 years", 0]
                ],
                "classed": "dashed",
                "key": "Children (0-6 years)"
            }]
        )

    def test_awc_reports_demographics_daily_keys(self):
        self.assertItemsEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 29),
                (2017, 5, 1),
            ),
            ['kpi', 'chart']
        )

    def test_awc_reports_demographics_daily_if_aggregation_script_fail_registered_households(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 30),
                (2017, 5, 1),
            )['kpi'][0][0],
            {
                "all": "",
                "format": "number",
                "color": "green",
                "percent": "Data in the previous reporting period was 0",
                "value": 139,
                "label": "Registered Households",
                "frequency": "day",
                "help_text": "Total number of households registered"
            }
        )

    def test_awc_reports_demographics_daily_if_aggregation_script_fail_percent_aadhaar_seeded_beneficiaries(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 30),
                (2017, 5, 1),
            )['kpi'][0][1],
            {
                "all": 5,
                'color': 'green',
                "format": "percent_and_div",
                "percent": "Data in the previous reporting period was 0",
                "value": 1,
                "label": "Percent Aadhaar-seeded Beneficiaries",
                "frequency": "day",
                "help_text": (
                    "Of the total number of ICDS beneficiaries, the percentage whose Adhaar identification "
                    "has been captured. "
                )
            }
        )

    def test_awc_reports_demographics_daily_if_aggregation_script_fail_percent_children_0_6_years_enrolled(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 30),
                (2017, 5, 1),
            )['kpi'][1][0],
            {
                "all": 0,
                "format": "percent_and_div",
                "color": "green",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": "Percent children (0-6 years) enrolled for Anganwadi Services",
                "frequency": "day",
                "help_text": percent_children_enrolled_help_text()
            }
        )

    def test_awc_reports_demographics_daily_if_aggregation_script_fail_percent_pregnant_women_enrolled(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 30),
                (2017, 5, 1),
            )['kpi'][1][1],
            {
                "all": 2,
                "format": "percent_and_div",
                "color": "green",
                "percent": "Data in the previous reporting period was 0",
                "value": 2,
                "label": "Percent pregnant women enrolled for Anganwadi Services",
                "frequency": "day",
                "help_text": percent_pregnant_women_enrolled_help_text()
            }
        )

    def test_awc_reports_demographics_daily_if_aggregation_script_fail_percent_lactating_women_enrolled(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 30),
                (2017, 5, 1),
            )['kpi'][2][0],
            {
                "all": 3,
                "format": "percent_and_div",
                "color": "green",
                "percent": "Data in the previous reporting period was 0",
                "value": 3,
                "label": "Percent lactating women enrolled for Anganwadi Services",
                "frequency": "day",
                "help_text": percent_lactating_women_enrolled_help_text()
            }
        )

    def test_awc_reports_demographics_daily_if_aggregation_script_fail_percent_adolescent_girls_enrolled(self):
        self.assertDictEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 30),
                (2017, 5, 1),
            )['kpi'][2][1],
            {
                "all": 0,
                "format": "percent_and_div",
                "color": "green",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
                "label": (
                    "Percent adolescent girls (11-14 years) enrolled for Anganwadi Services"
                ),
                "frequency": "day",
                "help_text": percent_adolescent_girls_enrolled_help_text()
            }
        )

    def test_awc_reports_demographics_daily_if_aggregation_script_fail_kpi_length(self):
        self.assertEqual(
            len(get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 30),
                (2017, 5, 1),
            )['kpi']),
            3
        )

    def test_awc_reports_demographics_daily_if_aggregation_script_fail_kpi_total_length(self):
        data = get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 30),
                (2017, 5, 1),
            )['kpi']

        self.assertEqual(
            sum([len(record_row) for record_row in data]),
            6
        )

    def test_awc_reports_demographics_daily_if_aggregation_script_fail_chart(self):
        self.assertEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 30),
                (2017, 5, 1),
            )['chart'],
            [{
                "values": [
                    ["0-1 month", 0],
                    ["1-6 months", 0],
                    ["6-12 months", 0],
                    ["1-3 years", 0],
                    ["3-6 years", 0]
                ],
                "classed": "dashed",
                "key": "Children (0-6 years)"
            }]
        )

    def test_awc_reports_demographics_daily_if_aggregation_script_fail_keys(self):
        self.assertItemsEqual(
            get_awc_report_demographics(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 30),
                (2017, 5, 1),
            ),
            ['kpi', 'chart']
        )

    def _get_beneficiary(self, case_id):
        return [
            row
            for row in get_awc_report_beneficiary(
                0, 100, 1, 'dob', {'awc_id': 'a18'}, (2017, 5, 1), (2017, 3, 1), False)['data']
            if row['case_id'] == case_id
        ][0]

    def test_awc_report_beneficiary_645fd452_3732_44fb_a2d3_46162304807e(self):
        data = self._get_beneficiary('645fd452-3732-44fb-a2d3-46162304807e')
        self.assertJSONEqual(
            json.dumps(data, cls=DjangoJSONEncoder),
            json.dumps(
                {
                    'recorded_weight': '9.9000000000000000',
                    'age_in_months': 17,
                    'current_month_stunting': {'color': 'black', 'value': 'Data Not Entered'},
                    'pse_days_attended': None,
                    'dob': '2015-12-15',
                    'age': '1 year 5 months ',
                    'current_month_wasting': {'color': 'black', 'value': 'Data Not Entered'},
                    'current_month_nutrition_status': {'color': 'black', 'value': 'Normal weight for age'},
                    'case_id': '645fd452-3732-44fb-a2d3-46162304807e',
                    'recorded_height': 0,
                    'fully_immunized': 'No',
                    'person_name': 'Name 1237',
                    'aww_phone_number': None,
                    'mother_phone_number': None
                },
                cls=DjangoJSONEncoder
            )
        )

    def test_awc_report_beneficiary_9ca36787_bed9_4af0_a13e_fca1c9cad360(self):
        data = self._get_beneficiary('9ca36787-bed9-4af0-a13e-fca1c9cad360')
        self.assertJSONEqual(
            json.dumps(data, cls=DjangoJSONEncoder),
            json.dumps(
                {
                    'recorded_weight': '6.2000000000000000',
                    'age_in_months': 5,
                    'current_month_stunting': {'color': 'black', 'value': 'Data Not Entered'},
                    'pse_days_attended': None,
                    'dob': '2016-12-16',
                    'age': '5 months ',
                    'current_month_wasting': {'color': 'black', 'value': 'Data Not Entered'},
                    'current_month_nutrition_status': {'color': 'black', 'value': 'Normal weight for age'},
                    'case_id': '9ca36787-bed9-4af0-a13e-fca1c9cad360',
                    'recorded_height': 0,
                    'fully_immunized': 'No',
                    'person_name': 'Name 1303',
                    'aww_phone_number': None,
                    'mother_phone_number': None
                },
                cls=DjangoJSONEncoder
            )
        )

    def test_awc_report_beneficiary_7673a69c_29af_478c_85c6_9c3b22f6b2e4(self):
        data = self._get_beneficiary('7673a69c-29af-478c-85c6-9c3b22f6b2e4')
        self.assertJSONEqual(
            json.dumps(data, cls=DjangoJSONEncoder),
            json.dumps(
                {
                    'recorded_weight': '11.0000000000000000',
                    'age_in_months': 14,
                    'current_month_stunting': {'color': 'black', 'value': 'Data Not Entered'},
                    'pse_days_attended': None,
                    'dob': '2016-03-06',
                    'age': '1 year 2 months ',
                    'current_month_wasting': {'color': 'black', 'value': 'Data Not Entered'},
                    'current_month_nutrition_status': {'color': 'black', 'value': 'Normal weight for age'},
                    'case_id': '7673a69c-29af-478c-85c6-9c3b22f6b2e4',
                    'recorded_height': 0,
                    'fully_immunized': 'No',
                    'person_name': 'Name 1305',
                    'aww_phone_number': None,
                    'mother_phone_number': None
                },
                cls=DjangoJSONEncoder
            )
        )

    def test_awc_report_beneficiary_d5d3fbeb_8b6a_486b_a853_30be35589200(self):
        data = self._get_beneficiary('d5d3fbeb-8b6a-486b-a853-30be35589200')
        self.assertJSONEqual(
            json.dumps(data, cls=DjangoJSONEncoder),
            json.dumps(
                {
                    'recorded_weight': '7.0000000000000000',
                    'age_in_months': 7,
                    'current_month_stunting': {'color': 'black', 'value': 'Data Not Entered'},
                    'pse_days_attended': None,
                    'dob': '2016-10-05',
                    'age': '7 months ',
                    'current_month_wasting': {'color': 'black', 'value': 'Data Not Entered'},
                    'current_month_nutrition_status': {'color': 'black', 'value': 'Normal weight for age'},
                    'case_id': 'd5d3fbeb-8b6a-486b-a853-30be35589200',
                    'recorded_height': 0,
                    'fully_immunized': 'No',
                    'person_name': 'Name 1341',
                    'aww_phone_number': None,
                    'mother_phone_number': None
                },
                cls=DjangoJSONEncoder
            )
        )

    def test_awc_report_beneficiary_b954eb28_75de_43c8_9ec0_d38b7d246ead(self):
        data = self._get_beneficiary('b954eb28-75de-43c8-9ec0-d38b7d246ead')
        self.assertJSONEqual(
            json.dumps(data, cls=DjangoJSONEncoder),
            json.dumps(
                {
                    'recorded_weight': '19.0000000000000000',
                    'age_in_months': 59,
                    'current_month_stunting': {'color': 'black', 'value': 'Data Not Entered'},
                    'pse_days_attended': 1,
                    'dob': '2012-06-26',
                    'age': '4 years 11 months ',
                    'current_month_wasting': {'color': 'black', 'value': 'Data Not Entered'},
                    'current_month_nutrition_status': {'color': 'black', 'value': 'Normal weight for age'},
                    'case_id': 'b954eb28-75de-43c8-9ec0-d38b7d246ead',
                    'recorded_height': 0,
                    'fully_immunized': 'No',
                    'person_name': 'Name 2617',
                    'aww_phone_number': None,
                    'mother_phone_number': None
                },
                cls=DjangoJSONEncoder
            )
        )

    def test_awc_report_beneficiary_532f3754_e231_40ec_a861_abbb2a06dff5(self):
        data = self._get_beneficiary('6faecfe6-cc88-4ff0-9b3d-d8ca069dd06f')
        self.assertJSONEqual(
            json.dumps(data, cls=DjangoJSONEncoder),
            json.dumps(
                {
                    'recorded_weight': '4.0000000000000000',
                    'age_in_months': 2,
                    'current_month_stunting': {'color': 'black', 'value': 'Data Not Entered'},
                    'pse_days_attended': None,
                    'dob': '2017-03-19',
                    'age': '2 months ',
                    'current_month_wasting': {'color': 'black', 'value': 'Data Not Entered'},
                    'current_month_nutrition_status': {'color': 'black', 'value': 'Normal weight for age'},
                    'case_id': '6faecfe6-cc88-4ff0-9b3d-d8ca069dd06f',
                    'recorded_height': 0,
                    'fully_immunized': 'No',
                    'person_name': 'Name 2917',
                    'aww_phone_number': None,
                    'mother_phone_number': None
                },
                cls=DjangoJSONEncoder
            )
        )

    def test_awc_report_beneficiary_3b242a3b_693e_44dd_ad4a_b713efdb0fdb(self):
        data = self._get_beneficiary('3b242a3b-693e-44dd-ad4a-b713efdb0fdb')
        self.assertJSONEqual(
            json.dumps(data, cls=DjangoJSONEncoder),
            json.dumps(
                {
                    'recorded_weight': '14.3000000000000000',
                    'age_in_months': 45,
                    'current_month_stunting': {'color': 'black', 'value': 'Data Not Entered'},
                    'pse_days_attended': 13,
                    'dob': '2013-08-22',
                    'age': '3 years 9 months ',
                    'current_month_wasting': {'color': 'black', 'value': 'Data Not Entered'},
                    'current_month_nutrition_status': {'color': 'black', 'value': 'Normal weight for age'},
                    'case_id': '3b242a3b-693e-44dd-ad4a-b713efdb0fdb',
                    'recorded_height': 0,
                    'fully_immunized': 'No',
                    'person_name': 'Name 4398',
                    'aww_phone_number': None,
                    'mother_phone_number': None},
                cls=DjangoJSONEncoder
            )
        )

    def test_awc_report_beneficiary_4cd07ebf_abce_4345_a930_f6db7ede8996(self):
        data = self._get_beneficiary('4cd07ebf-abce-4345-a930-f6db7ede8996')
        self.assertJSONEqual(
            json.dumps(data, cls=DjangoJSONEncoder),
            json.dumps(
                {
                    'recorded_weight': '14.5000000000000000',
                    'age_in_months': 57,
                    'current_month_stunting': {'color': 'black', 'value': 'Data Not Entered'},
                    'pse_days_attended': 9,
                    'dob': '2012-08-24',
                    'age': '4 years 9 months ',
                    'current_month_wasting': {'color': 'black', 'value': 'Data Not Entered'},
                    'current_month_nutrition_status': {'color': 'black', 'value': 'Normal weight for age'},
                    'case_id': '4cd07ebf-abce-4345-a930-f6db7ede8996',
                    'recorded_height': 0,
                    'fully_immunized': 'No',
                    'person_name': 'Name 4399',
                    'aww_phone_number': None,
                    'mother_phone_number': None
                },
                cls=DjangoJSONEncoder
            )
        )

    def test_awc_report_beneficiary_0198ec4a_f5ed_4452_863c_a400f43d238a(self):
        data = self._get_beneficiary('0198ec4a-f5ed-4452-863c-a400f43d238a')
        self.assertJSONEqual(
            json.dumps(data, cls=DjangoJSONEncoder),
            json.dumps(
                {
                    'recorded_weight': '13.3000000000000000',
                    'age_in_months': 49,
                    'current_month_stunting': {'color': 'black', 'value': 'Data Not Entered'},
                    'pse_days_attended': 11,
                    'dob': '2013-05-01',
                    'age': '4 years ',
                    'current_month_wasting': {'color': 'black', 'value': 'Data Not Entered'},
                    'current_month_nutrition_status': {'color': 'black', 'value': 'Normal weight for age'},
                    'case_id': '0198ec4a-f5ed-4452-863c-a400f43d238a',
                    'recorded_height': 0,
                    'fully_immunized': 'No',
                    'person_name': 'Name 4400',
                    'aww_phone_number': None,
                    'mother_phone_number': None
                },
                cls=DjangoJSONEncoder
            )
        )

    def test_awc_report_beneficiary_a9dc5cac_6820_45cf_b8c9_16f2cfb0ae02(self):
        data = self._get_beneficiary('a9dc5cac-6820-45cf-b8c9-16f2cfb0ae02')
        self.assertJSONEqual(
            json.dumps(data, cls=DjangoJSONEncoder),
            json.dumps(
                {
                    'recorded_weight': '6.8000000000000000',
                    'age_in_months': 6,
                    'current_month_stunting': {'color': 'black', 'value': 'Data Not Entered'},
                    'pse_days_attended': None,
                    'dob': '2016-11-16',
                    'age': '6 months ',
                    'current_month_wasting': {'color': 'black', 'value': 'Data Not Entered'},
                    'current_month_nutrition_status': {'color': 'black', 'value': 'Normal weight for age'},
                    'case_id': 'a9dc5cac-6820-45cf-b8c9-16f2cfb0ae02',
                    'recorded_height': 0,
                    'fully_immunized': 'No',
                    'person_name': 'Name 1191',
                    'aww_phone_number': None,
                    'mother_phone_number': None
                },
                cls=DjangoJSONEncoder
            )
        )

    def test_awc_report_beneficiary_data_length(self):
        data = get_awc_report_beneficiary(0, 10, 1, 'dob', {'awc_id': 'a18'}, (2017, 5, 1), (2017, 3, 1), False)
        self.assertEqual(
            len(data['data']),
            10
        )

    def test_awc_report_beneficiary_data_without_data(self):
        data = get_awc_report_beneficiary(0, 10, 1, 'dob', {'awc_id': 'a18'}, (2017, 5, 1), (2017, 3, 1), False)
        del data['data']
        self.assertJSONEqual(
            json.dumps(data, cls=DjangoJSONEncoder),
            json.dumps({
                "draw": 1,
                "last_month": "May 2017",
                "recordsTotal": 27,
                "months": [
                    "May 2017",
                    "Apr 2017",
                    "Mar 2017"
                ],
                "recordsFiltered": 27,
            }, cls=DjangoJSONEncoder)
        )

    def test_awc_report_beneficiary_keys(self):
        data = get_awc_report_beneficiary(0, 10, 1, 'dob', {'awc_id': 'a18'}, (2017, 5, 1), (2017, 3, 1), False)
        self.assertItemsEqual(
            data,
            ['draw', 'last_month', 'recordsTotal', 'months', 'recordsFiltered', 'data']
        )

    def test_awc_report_pregnant_first_record(self):
        with mock.patch('custom.icds_reports.reports.awc_reports.date', FirstDayOfMayDate):
            data = get_awc_report_pregnant(
                start=0,
                length=10,
                order='age',
                reversed_order=False,
                awc_id='a15'
            )

            self.assertEqual(
                len(data['data']),
                2
            )

            self.assertEqual(
                data['data'][0],
                {
                    'age': 23,
                    'closed': None,
                    'beneficiary': 'Yes',
                    'anemic': 'Data Not Entered',
                    'case_id': '7313c174-6b63-457c-a734-6eed0a2b2ac6',
                    'edd': datetime.date(2017, 8, 31),
                    'last_date_thr': None,
                    'num_anc_complete': None,
                    'number_of_thrs_given': 0,
                    'opened_on': datetime.date(2017, 5, 12),
                    'person_name': None,
                    'trimester': 2,
                }
            )

    def test_pregnant_details_first_record_first_trimester(self):
        with mock.patch('custom.icds_reports.reports.awc_reports.datetime', FirstDayOfMay):
            data = get_pregnant_details(
                case_id='7313c174-6b63-457c-a734-6eed0a2b2ac6',
                awc_id='a15'
            )
            self.assertEqual(
                data['data'][0],
                []
            )

    def test_pregnant_details_first_record_second_trimester(self):
        with mock.patch('custom.icds_reports.reports.awc_reports.datetime', FirstDayOfMay):
            data = get_pregnant_details(
                case_id='7313c174-6b63-457c-a734-6eed0a2b2ac6',
                awc_id='a15'
            )
            self.assertEqual(
                data['data'][1],
                [
                    {'opened_on': datetime.date(2017, 5, 12),
                     'tt_taken': 'N',
                     'person_name': 'Data Not Entered',
                     'anc_weight': 'Data Not Entered',
                     'edd': datetime.date(2017, 8, 31),
                     'age': 23,
                     'tt_date': 'None',
                     'anc_hemoglobin': 'Data Not Entered',
                     'symptoms': 'None',
                     'preg_order': 'Data Not Entered',
                     'using_ifa': 'Y',
                     'case_id': '7313c174-6b63-457c-a734-6eed0a2b2ac6',
                     'bp': 'Data Not Entered',
                     'ifa_consumed_last_seven_days': 'Y',
                     'mobile_number': 'Data Not Entered',
                     'trimester': 2,
                     'counseling': 'Eating Extra, Taking Rest',
                     'anc_abnormalities': 'None',
                     'anemic': 'Data Not Entered',
                     'home_visit_date': datetime.date(2017, 5, 4)}]
            )

    def test_pregnant_details_first_record_third_trimester(self):
        with mock.patch('custom.icds_reports.reports.awc_reports.datetime', FirstDayOfMay):
            data = get_pregnant_details(
                case_id='7313c174-6b63-457c-a734-6eed0a2b2ac6',
                awc_id='a15'
            )
            self.assertEqual(
                data['data'][2],
                []
            )

    def test_awc_report_lactating_first_record(self):
        with mock.patch('custom.icds_reports.reports.awc_reports.datetime', SecondDayOfMay):
            data = get_awc_report_lactating(
                start=0,
                length=10,
                order='age',
                reversed_order=False,
                awc_id='a50'
            )
            self.assertEqual(
                data['data'][0],
                {
                    'num_rations_distributed': 0,
                    'institutional_delivery': 'N',
                    'person_name': None,
                    'delivery_nature': 'Data Not Entered',
                    'age': 20,
                    'num_pnc_visits': None,
                    'add': datetime.date(2017, 3, 1),
                    'case_id': '36d5e223-a631-4030-910c-262a1d066fb3',
                    'breastfed_at_birth': 'N',
                    'is_ebf': 'N'}
            )

    def test_awc_report_lactating_second_record(self):
        with mock.patch('custom.icds_reports.reports.awc_reports.datetime', SecondDayOfMay):
            data = get_awc_report_lactating(
                start=0,
                length=10,
                order='age',
                reversed_order=False,
                awc_id='a50'
            )
            self.assertEqual(
                data['data'][1],
                {
                    'num_rations_distributed': 6,
                    'institutional_delivery': 'N',
                    'person_name': None,
                    'delivery_nature': 'Data Not Entered',
                    'age': 23,
                    'num_pnc_visits': None,
                    'add': datetime.date(2017, 4, 20),
                    'case_id': 'aefb8fe5-1cd1-4235-9baf-963b1a0b498e',
                    'breastfed_at_birth': 'N',
                    'is_ebf': 'N'}
            )

    def test_awc_report_lactating_third_record(self):
        with mock.patch('custom.icds_reports.reports.awc_reports.datetime', SecondDayOfMay):
            data = get_awc_report_lactating(
                start=0,
                length=10,
                order='age',
                reversed_order=False,
                awc_id='a50'
            )
            self.assertEqual(
                data['data'][2],
                {
                    'num_rations_distributed': 6,
                    'institutional_delivery': 'N',
                    'person_name': None,
                    'delivery_nature': 'Data Not Entered',
                    'age': 24,
                    'num_pnc_visits': None,
                    'add': datetime.date(2017, 3, 1),
                    'case_id': '4f0aac21-5b5d-43a6-a1f6-9744d0e66cf2',
                    'breastfed_at_birth': 'N',
                    'is_ebf': 'N'}
            )

    def test_awc_report_lactating_forth_record(self):
        with mock.patch('custom.icds_reports.reports.awc_reports.datetime', SecondDayOfMay):
            data = get_awc_report_lactating(
                start=0,
                length=10,
                order='age',
                reversed_order=False,
                awc_id='a50'
            )
            self.assertEqual(
                data['data'][3],
                {
                    'num_rations_distributed': 12,
                    'institutional_delivery': 'N',
                    'person_name': None,
                    'delivery_nature': 'Data Not Entered',
                    'age': 26,
                    'num_pnc_visits': None,
                    'add': datetime.date(2017, 3, 20),
                    'case_id': '10a53900-f65e-46b7-ae0c-f32a208c0677',
                    'breastfed_at_birth': 'N',
                    'is_ebf': 'N'}
            )

    def test_awc_report_lactating_fifth_record(self):
        with mock.patch('custom.icds_reports.reports.awc_reports.datetime', SecondDayOfMay):
            data = get_awc_report_lactating(
                start=0,
                length=10,
                order='age',
                reversed_order=False,
                awc_id='a50'
            )
            self.assertEqual(
                data['data'][4],
                {
                    'num_rations_distributed': 12,
                    'institutional_delivery': 'N',
                    'person_name': None,
                    'delivery_nature': 'Data Not Entered',
                    'age': 26,
                    'num_pnc_visits': None,
                    'add': datetime.date(2017, 3, 1),
                    'case_id': '1a6851bc-8172-48fc-80d1-b198f23033ab',
                    'breastfed_at_birth': 'N',
                    'is_ebf': 'N'}
            )

    def test_awc_report_lactating_sixth_record(self):
        with mock.patch('custom.icds_reports.reports.awc_reports.datetime', SecondDayOfMay):
            data = get_awc_report_lactating(
                start=0,
                length=10,
                order='age',
                reversed_order=False,
                awc_id='a50'
            )
            self.assertEqual(
                data['data'][5],
                {
                    'num_rations_distributed': 6,
                    'institutional_delivery': 'N',
                    'person_name': None,
                    'delivery_nature': 'Data Not Entered',
                    'age': 26,
                    'num_pnc_visits': None,
                    'add': datetime.date(2017, 3, 1),
                    'case_id': '37c4d26f-eda0-4d9a-bae9-11a17a3ccfaa',
                    'breastfed_at_birth': 'N',
                    'is_ebf': 'N'}
            )

    def test_awc_report_lactating_seventh_record(self):
        with mock.patch('custom.icds_reports.reports.awc_reports.datetime', SecondDayOfMay):
            data = get_awc_report_lactating(
                start=0,
                length=10,
                order='age',
                reversed_order=False,
                awc_id='a50'
            )

            self.assertEqual(
                data['data'][6],
                {
                    'num_rations_distributed': 6,
                    'institutional_delivery': 'N',
                    'person_name': None,
                    'delivery_nature': 'Data Not Entered',
                    'age': 29,
                    'num_pnc_visits': None,
                    'add': datetime.date(2017, 3, 1),
                    'case_id': '1744a035-56f1-4059-86f5-93fcea3c6076',
                    'breastfed_at_birth': 'N',
                    'is_ebf': 'N'}
            )

    def test_awc_report_lactating_on_first_of_month(self):
        with mock.patch('custom.icds_reports.reports.awc_reports.datetime', FirstDayOfMay):
            data = get_awc_report_lactating(
                start=0,
                length=7,
                order='age',
                reversed_order=False,
                awc_id='a50'
            )
            self.assertListEqual(
                data['data'],
                [
                    {'num_rations_distributed': 0, 'person_name': None, 'num_pnc_visits': None,
                     'age': 20, 'delivery_nature': u'Data Not Entered', 'add': datetime.date(2017, 3, 1),
                     'case_id': u'36d5e223-a631-4030-910c-262a1d066fb3', 'breastfed_at_birth': u'N',
                     'is_ebf': u'N', 'institutional_delivery': u'N'},
                    {'num_rations_distributed': 0, 'person_name': None, 'num_pnc_visits': None,
                     'age': 23, 'delivery_nature': u'Data Not Entered', 'add': datetime.date(2017, 4, 20),
                     'case_id': u'aefb8fe5-1cd1-4235-9baf-963b1a0b498e', 'breastfed_at_birth': u'N',
                     'is_ebf': u'N', 'institutional_delivery': u'N'},
                    {'num_rations_distributed': 0, 'person_name': None, 'num_pnc_visits': None, 'age': 24,
                     'delivery_nature': u'Data Not Entered', 'add': datetime.date(2017, 3, 1),
                     'case_id': u'4f0aac21-5b5d-43a6-a1f6-9744d0e66cf2', 'breastfed_at_birth': u'N',
                     'is_ebf': u'N', 'institutional_delivery': u'N'},
                    {'num_rations_distributed': 0, 'person_name': None, 'num_pnc_visits': None, 'age': 26,
                     'delivery_nature': u'Data Not Entered', 'add': datetime.date(2017, 3, 20),
                     'case_id': u'10a53900-f65e-46b7-ae0c-f32a208c0677', 'breastfed_at_birth': u'N',
                     'is_ebf': u'N', 'institutional_delivery': u'N'},
                    {'num_rations_distributed': 0, 'person_name': None, 'num_pnc_visits': None, 'age': 26,
                     'delivery_nature': u'Data Not Entered', 'add': datetime.date(2017, 3, 1),
                     'case_id': u'1a6851bc-8172-48fc-80d1-b198f23033ab', 'breastfed_at_birth': u'N',
                     'is_ebf': u'N', 'institutional_delivery': u'N'},
                    {'num_rations_distributed': 0, 'person_name': None, 'num_pnc_visits': None, 'age': 26,
                     'delivery_nature': u'Data Not Entered', 'add': datetime.date(2017, 3, 1),
                     'case_id': u'37c4d26f-eda0-4d9a-bae9-11a17a3ccfaa', 'breastfed_at_birth': u'N',
                     'is_ebf': u'N', 'institutional_delivery': u'N'},
                    {'num_rations_distributed': 0, 'person_name': None, 'num_pnc_visits': None, 'age': 29,
                     'delivery_nature': u'Data Not Entered', 'add': datetime.date(2017, 3, 1),
                     'case_id': u'1744a035-56f1-4059-86f5-93fcea3c6076', 'breastfed_at_birth': u'N',
                     'is_ebf': u'N', 'institutional_delivery': u'N'}
                ]
            )
