# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.test import TestCase

from custom.icds_reports.reports.awc_reports import get_beneficiary_details, get_awc_reports_system_usage, \
    get_awc_reports_pse, get_awc_reports_maternal_child, get_awc_report_demographics, \
    get_awc_report_infrastructure, get_awc_report_beneficiary


class TestAWCReport(TestCase):
    def test_beneficiary_details_recorded_weight_none(self):
        data = get_beneficiary_details(case_id='6b234c5b-883c-4849-9dfd-b1571af8717b')
        self.assertEqual(data['age_in_months'], 69)
        self.assertEqual(data['sex'], 'M')
        self.assertEqual(data['person_name'], 'Name 3342')
        self.assertEqual(data['mother_name'], 'संगीता')

    def test_beneficiary_details_recorded_weight_is_not_none(self):
        data = get_beneficiary_details(case_id='8e226cc6-740f-4146-b017-69d9f6e9651b')
        self.assertEqual(data['age_in_months'], 54)
        self.assertEqual(data['sex'], 'M')
        self.assertEqual(data['person_name'], 'Name 3141')
        self.assertEqual(data['mother_name'], 'शियामु बाई')
        self.assertEqual(filter(lambda r: r['x'] == 53, data['weight'])[0]['y'], 12.6)
        self.assertEqual(filter(lambda r: r['x'] == 53, data['height'])[0]['y'], 96.0)
        self.assertEqual(filter(lambda r: r['x'] == 96.0, data['wfl'])[0]['y'], 12.6)

    def test_beneficiary_details_have_age_in_month_not_have_recorded_height(self):
        data = get_beneficiary_details(case_id='411c4234-8475-415a-9c28-911b85868aa5')
        self.assertEqual(data['age_in_months'], 37)
        self.assertEqual(data['sex'], 'F')
        self.assertEqual(data['person_name'], 'Name 3483')
        self.assertEqual(data['mother_name'], u'रींकीकुँवर')

    def test_awc_reports_system_usage(self):
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
            ),
            {
                "kpi": [
                    [
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
                        },
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
                    ]
                ],
                "charts": [
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
                    ],
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
                ]
            }
        )

    def test_awc_reports_pse(self):
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
            data,
            {
                "images": [
                    [
                        {
                            "date": "01/05/2017",
                            "image": None,
                            "id": 0
                        },
                        {
                            "date": "02/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "00a368e6-e88f-41ee-96aa-25a8ec5ab3d6/1493703284010.jpg",
                            "id": 1
                        },
                        {
                            "date": "03/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "ef336dda-12a1-42a4-9bee-405d17c2aba8/1493790538044.jpg",
                            "id": 2
                        },
                        {
                            "date": "04/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "00ec149e-c1a9-4083-a73c-cdc39df17137/1493876634200.jpg",
                            "id": 3
                        }
                    ],
                    [
                        {
                            "date": "05/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
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
                    ],
                    [
                        {
                            "date": "09/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
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
                    ],
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
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "036ab123-0a1e-43b6-8e7d-4bcf9abcdfa2/1494826363729.jpg",
                            "id": 14
                        },
                        {
                            "date": "16/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "dda9c427-4ba7-4f90-9c5b-d2a02cff9e31/1494911839185.jpg",
                            "id": 15
                        }
                    ],
                    [
                        {
                            "date": "17/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "1be8a49b-c63c-4288-bcb2-9e5bf132834f/1494997946602.jpg",
                            "id": 16
                        },
                        {
                            "date": "18/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "c7f6d174-1218-4f8e-ab84-f80e17b1ebdb/1495084707730.jpg",
                            "id": 17
                        },
                        {
                            "date": "19/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "416990d9-f354-457f-8c52-1866e98840f5/1495173038810.jpg",
                            "id": 18
                        },
                        {
                            "date": "20/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "3fea99f8-c6f4-48c9-9386-152639fe1b17/1495259635314.jpg",
                            "id": 19
                        }
                    ],
                    [
                        {
                            "date": "21/05/2017",
                            "image": None,
                            "id": 20
                        },
                        {
                            "date": "22/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
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
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "5d0f2aa4-6d5b-424f-91d1-c4afb2d0555b/1495605536823.jpg",
                            "id": 23
                        }
                    ],
                    [
                        {
                            "date": "25/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "20e4d641-a85a-4927-96ab-994fa46a8ea0/1495690578649.jpg",
                            "id": 24
                        },
                        {
                            "date": "26/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "f86e701b-1531-469f-8996-705e297bf498/1495776461721.jpg",
                            "id": 25
                        },
                        {
                            "date": "27/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "6701b39d-4b6f-4ae3-8a88-eadb61b1a105/1495865744995.jpg",
                            "id": 26
                        },
                        {
                            "date": "28/05/2017",
                            "image": None,
                            "id": 27
                        }
                    ],
                    [
                        {
                            "date": "29/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "6376d77d-bb2a-48ac-9042-7892dda97bba/1496036503892.jpg",
                            "id": 28
                        },
                        {
                            "date": "30/05/2017",
                            "image": "http://localhost:8000/a/icds-cas/api/form/attachment/"
                                     "c0d002ca-f7b0-4bd2-a531-881b46610c2f/1496120210768.jpg",
                            "id": 29
                        },
                        {
                            "date": "31/05/2017",
                            "image": None,
                            "id": 30
                        }
                    ]
                ],
                "kpi": [
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
                ],
                "charts": [
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
                    ],
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
                ],
                "map": {
                    "markers": {}
                }
            }
        )

    def test_awc_reports_maternal_child(self):
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
        self.assertDictEqual(
            data,
            {
                "kpi": [
                    [
                        {
                            "color": "red",
                            "all": 0,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": "Underweight (Weight-for-Age)"
                        },
                        {
                            "color": "red",
                            "all": 0,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": "Wasting (Weight-for-Height)"
                        }
                    ],
                    [
                        {
                            "color": "red",
                            "all": 0,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": "Stunting (Height-for-Age)"
                        },
                        {
                            "color": "green",
                            "all": 0,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": "Weighing Efficiency"
                        }
                    ],
                    [
                        {
                            "color": "red",
                            "all": 0,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": "Newborns with Low Birth Weight"
                        },
                        {
                            "color": "green",
                            "all": 0,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": "Early Initiation of Breastfeeding"
                        }
                    ],
                    [
                        {
                            "color": "green",
                            "all": 0,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": "Exclusive breastfeeding"
                        },
                        {
                            "color": "green",
                            "all": 0,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": "Children initiated appropriate Complementary Feeding"
                        }
                    ],
                    [
                        {
                            "color": "green",
                            "all": 0,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": "Immunization Coverage (at age 1 year)"
                        },
                        {
                            "color": "green",
                            "all": 0,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": "Institutional Deliveries"
                        }
                    ]
                ]
            }
        )

    def test_awc_reports_demographics_monthly(self):
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
            ),
            {
                "kpi": [
                    [
                        {
                            "all": "",
                            "format": "number",
                            "color": "red",
                            "percent": 0.0,
                            "value": 139,
                            "label": "Registered Households",
                            "frequency": "month",
                            "help_text": "Total number of households registered"
                        },
                        {
                            "all": 6,
                            "format": "percent_and_div",
                            "percent": -33.33333333333334,
                            "value": 1,
                            "label": "Percent Aadhaar-seeded Beneficiaries",
                            "frequency": "month",
                            "help_text": "Percentage of ICDS beneficiaries whose Aadhaar"
                                         " identification has been captured"
                        }
                    ],
                    [
                        {
                            "all": 0,
                            "format": "percent_and_div",
                            "color": "green",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": "Percent children (0-6 years) enrolled for ICDS services",
                            "frequency": "month",
                            "help_text": "Percentage of children registered between 0-6 years old "
                                         "who are enrolled for ICDS services"
                        },
                        {
                            "all": 2,
                            "format": "percent_and_div",
                            "color": "red",
                            "percent": 0.0,
                            "value": 2,
                            "label": "Percent pregnant women enrolled for ICDS services",
                            "frequency": "month",
                            "help_text": "Percentage of pregnant women registered "
                                         "who are enrolled for ICDS services"
                        }
                    ],
                    [
                        {
                            "all": 3,
                            "format": "percent_and_div",
                            "color": "red",
                            "percent": 0.0,
                            "value": 3,
                            "label": "Percent lactating women enrolled for ICDS services",
                            "frequency": "month",
                            "help_text": "Percentage of lactating women registered "
                                         "who are enrolled for ICDS services"
                        },
                        {
                            "all": 0,
                            "format": "percent_and_div",
                            "color": "red",
                            "percent": -100.0,
                            "value": 0,
                            "label": "Percent adolescent girls (11-18 years) enrolled for ICDS services",
                            "frequency": "month",
                            "help_text": "Percentage of adolescent girls registered between"
                                         " 11-18 years old who are enrolled for ICDS services"
                        }
                    ]
                ],
                "chart": [
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
            }
        )

    def test_awc_reports_demographics_daily(self):
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
            ),
            {
                "kpi": [
                    [
                        {
                            "all": "",
                            "format": "number",
                            "color": "green",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 139,
                            "label": "Registered Households",
                            "frequency": "day",
                            "help_text": "Total number of households registered"
                        },
                        {
                            "all": 6,
                            "format": "percent_and_div",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 1,
                            "label": "Percent Aadhaar-seeded Beneficiaries",
                            "frequency": "day",
                            "help_text": (
                                "Percentage of ICDS beneficiaries whose Aadhaar identification has been captured"
                            )
                        }
                    ],
                    [
                        {
                            "all": 0,
                            "format": "percent_and_div",
                            "color": "green",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": "Percent children (0-6 years) enrolled for ICDS services",
                            "frequency": "day",
                            "help_text": (
                                "Percentage of children registered between 0-6 years old "
                                "who are enrolled for ICDS services"
                            )
                        },
                        {
                            "all": 2,
                            "format": "percent_and_div",
                            "color": "green",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 2,
                            "label": "Percent pregnant women enrolled for ICDS services",
                            "frequency": "day",
                            "help_text": (
                                "Percentage of pregnant women registered who are enrolled for ICDS services"
                            )
                        }
                    ],
                    [
                        {
                            "all": 3,
                            "format": "percent_and_div",
                            "color": "green",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 3,
                            "label": "Percent lactating women enrolled for ICDS services",
                            "frequency": "day",
                            "help_text": (
                                "Percentage of lactating women registered who are enrolled for ICDS services"
                            )
                        },
                        {
                            "all": 0,
                            "format": "percent_and_div",
                            "color": "green",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": (
                                "Percent adolescent girls (11-18 years) enrolled for ICDS services"
                            ),
                            "frequency": "day",
                            "help_text": (
                                "Percentage of adolescent girls registered between 11-18 years old who "
                                "are enrolled for ICDS services"
                            )
                        }
                    ]
                ],
                "chart": [{
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
            }

        )

    def test_awc_reports_demographics_daily_if_aggregation_script_fail(self):
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
            ),
            {
                "kpi": [
                    [
                        {
                            "all": "",
                            "format": "number",
                            "color": "green",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 139,
                            "label": "Registered Households",
                            "frequency": "day",
                            "help_text": "Total number of households registered"
                        },
                        {
                            "all": 6,
                            "format": "percent_and_div",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 1,
                            "label": "Percent Aadhaar-seeded Beneficiaries",
                            "frequency": "day",
                            "help_text": (
                                "Percentage of ICDS beneficiaries whose Aadhaar identification has been captured"
                            )
                        }
                    ],
                    [
                        {
                            "all": 0,
                            "format": "percent_and_div",
                            "color": "green",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": "Percent children (0-6 years) enrolled for ICDS services",
                            "frequency": "day",
                            "help_text": (
                                "Percentage of children registered between 0-6 years old "
                                "who are enrolled for ICDS services"
                            )
                        },
                        {
                            "all": 2,
                            "format": "percent_and_div",
                            "color": "green",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 2,
                            "label": "Percent pregnant women enrolled for ICDS services",
                            "frequency": "day",
                            "help_text": (
                                "Percentage of pregnant women registered who are enrolled for ICDS services"
                            )
                        }
                    ],
                    [
                        {
                            "all": 3,
                            "format": "percent_and_div",
                            "color": "green",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 3,
                            "label": "Percent lactating women enrolled for ICDS services",
                            "frequency": "day",
                            "help_text": (
                                "Percentage of lactating women registered who are enrolled for ICDS services"
                            )
                        },
                        {
                            "all": 0,
                            "format": "percent_and_div",
                            "color": "green",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 0,
                            "label": (
                                "Percent adolescent girls (11-18 years) enrolled for ICDS services"
                            ),
                            "frequency": "day",
                            "help_text": (
                                "Percentage of adolescent girls registered between 11-18 years old who "
                                "are enrolled for ICDS services"
                            )
                        }
                    ]
                ],
                "chart": [{
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
            }

        )

    def test_awc_reports_infrastructure(self):
        self.assertDictEqual(
            get_awc_report_infrastructure(
                'icds-cas',
                {
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'awc_id': 'a1',
                    'aggregation_level': 5
                },
                (2017, 5, 1),
            ),
            {
                "kpi": [
                    [
                        {
                            "all": "",
                            "format": "string",
                            "show_percent": False,
                            "value": "Available",
                            "label": "Clean Drinking Water",
                            "frequency": "month",
                            "help_text": None
                        },
                        {
                            "all": "",
                            "format": "string",
                            "show_percent": False,
                            "value": "Available",
                            "label": "Functional Toilet",
                            "frequency": "month",
                            "help_text": None
                        }
                    ],
                    [
                        {
                            "all": "",
                            "format": "string",
                            "show_percent": False,
                            "value": "Data not Entered",
                            "label": "Weighing Scale: Infants",
                            "frequency": "month",
                            "help_text": None
                        },
                        {
                            "all": "",
                            "format": "string",
                            "show_percent": False,
                            "value": "Data not Entered",
                            "label": "AWCs with Weighing Scale: Mother and Child",
                            "frequency": "month",
                            "help_text": None
                        }
                    ],
                    [
                        {
                            "all": "",
                            "format": "string",
                            "show_percent": False,
                            "value": "Data not Entered",
                            "label": "Medicine Kit",
                            "frequency": "month",
                            "help_text": None
                        }
                    ]
                ]
            }
        )

    def test_awc_report_beneficiary(self):
        data = get_awc_report_beneficiary(0, 10, 1, 'dob', 'a18', (2017, 5, 1), (2017, 3, 1))
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
                "data": [
                    {
                        "recorded_weight": "12.8000000000000000",
                        "age_in_months": 59,
                        "current_month_stunting": {
                            "color": "black",
                            "value": "Moderately stunted"
                        },
                        "pse_days_attended": 14,
                        "dob": "2012-06-03",
                        "age": "4 years 11 months ",
                        "current_month_wasting": {
                            "color": "black",
                            "value": "Normal height for age"
                        },
                        "current_month_nutrition_status": {
                            "color": "black",
                            "value": "Moderately underweight"
                        },
                        "case_id": "ca040875-2e42-4ce4-acf7-f96695b370f1",
                        "recorded_height": "95.0000000000000000",
                        "fully_immunized": "No",
                        "person_name": "Name 4416",
                        "sex": "F",
                        "mother_name": "रामकन्या"
                    }, {
                        "recorded_weight": "14.3000000000000000",
                        "age_in_months": 59,
                        "current_month_stunting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "pse_days_attended": 14,
                        "dob": "2012-06-23",
                        "age": "4 years 11 months ",
                        "current_month_wasting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "current_month_nutrition_status": {
                            "color": "black",
                            "value": "Normal weight for age"
                        },
                        "case_id": "82f33fa1-2aec-45ba-8d6c-d3ca9f50ab73",
                        "recorded_height": 0,
                        "fully_immunized": "No",
                        "person_name": "Name 4445",
                        "sex": "F",
                        "mother_name": "किरणबाई"
                    }, {
                        "recorded_weight": "19.0000000000000000",
                        "age_in_months": 59,
                        "current_month_stunting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "pse_days_attended": 1,
                        "dob": "2012-06-26",
                        "age": "4 years 11 months ",
                        "current_month_wasting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "current_month_nutrition_status": {
                            "color": "black",
                            "value": "Normal weight for age"
                        },
                        "case_id": "b954eb28-75de-43c8-9ec0-d38b7d246ead",
                        "recorded_height": 0,
                        "fully_immunized": "No",
                        "person_name": "Name 2617",
                        "sex": "M",
                        "mother_name": "ताराकुँवर पति राजेन्द्रसिंह"
                    }, {
                        "recorded_weight": "14.6000000000000000",
                        "age_in_months": 58,
                        "current_month_stunting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "pse_days_attended": 14,
                        "dob": "2012-07-05",
                        "age": "4 years 10 months ",
                        "current_month_wasting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "current_month_nutrition_status": {
                            "color": "black",
                            "value": "Normal weight for age"
                        },
                        "case_id": "519720be-4343-41e7-a9f6-cdfad6ecf8d8",
                        "recorded_height": 0,
                        "fully_immunized": "No",
                        "person_name": "Name 4412",
                        "sex": "M",
                        "mother_name": "जशोदा"
                    }, {
                        "recorded_weight": "14.8000000000000000",
                        "age_in_months": 58,
                        "current_month_stunting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "pse_days_attended": 16,
                        "dob": "2012-07-18",
                        "age": "4 years 10 months ",
                        "current_month_wasting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "current_month_nutrition_status": {
                            "color": "black",
                            "value": "Normal weight for age"
                        },
                        "case_id": "80099a73-b7ec-4de9-a402-459ed15f6641",
                        "recorded_height": 0,
                        "fully_immunized": "No",
                        "person_name": "Name 4411",
                        "sex": "F",
                        "mother_name": "लक्ष्मी बाई"
                    }, {
                        "recorded_weight": "13.5000000000000000",
                        "age_in_months": 58,
                        "current_month_stunting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "pse_days_attended": 10,
                        "dob": "2012-07-19",
                        "age": "4 years 10 months ",
                        "current_month_wasting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "current_month_nutrition_status": {
                            "color": "black",
                            "value": "Moderately underweight"
                        },
                        "case_id": "532f3754-e231-40ec-a861-abbb2a06dff5",
                        "recorded_height": 0,
                        "fully_immunized": "No",
                        "person_name": "Name 4408",
                        "sex": "F",
                        "mother_name": "छनुकुवर पति चोकसिंह"
                    }, {
                        "recorded_weight": "14.5000000000000000",
                        "age_in_months": 57,
                        "current_month_stunting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "pse_days_attended": 9,
                        "dob": "2012-08-24",
                        "age": "4 years 9 months ",
                        "current_month_wasting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "current_month_nutrition_status": {
                            "color": "black",
                            "value": "Normal weight for age"
                        },
                        "case_id": "4cd07ebf-abce-4345-a930-f6db7ede8996",
                        "recorded_height": 0,
                        "fully_immunized": "No",
                        "person_name": "Name 4399",
                        "sex": "F",
                        "mother_name": "संगीताबाई पति धनसिंह"
                    }, {
                        "recorded_weight": "11.0000000000000000",
                        "age_in_months": 52,
                        "current_month_stunting": {
                            "color": "black",
                            "value": "Moderately stunted"
                        },
                        "pse_days_attended": 17,
                        "dob": "2013-01-02",
                        "age": "4 years 4 months ",
                        "current_month_wasting": {
                            "color": "black",
                            "value": "Moderately wasted"
                        },
                        "current_month_nutrition_status": {
                            "color": "red",
                            "value": "Severely underweight"
                        },
                        "case_id": "c9ee2435-d7fc-4307-9c18-9d5d83d2a691",
                        "recorded_height": "94.0000000000000000",
                        "fully_immunized": "No",
                        "person_name": "Name 4402",
                        "sex": "M",
                        "mother_name": "पोपा बाई"
                    }, {
                        "recorded_weight": "14.8000000000000000",
                        "age_in_months": 51,
                        "current_month_stunting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "pse_days_attended": 13,
                        "dob": "2013-02-07",
                        "age": "4 years 3 months ",
                        "current_month_wasting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "current_month_nutrition_status": {
                            "color": "black",
                            "value": "Normal weight for age"
                        },
                        "case_id": "d44f7902-83d4-4f1d-a913-4176cf41094e",
                        "recorded_height": 0,
                        "fully_immunized": "No",
                        "person_name": "Name 4414",
                        "sex": "M",
                        "mother_name": "भूराकुवर पति धर्मेन्द्रसिंह"
                    }, {
                        "recorded_weight": "12.6000000000000000",
                        "age_in_months": 51,
                        "current_month_stunting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "pse_days_attended": 9,
                        "dob": "2013-02-11",
                        "age": "4 years 3 months ",
                        "current_month_wasting": {
                            "color": "black",
                            "value": "Data Not Entered"
                        },
                        "current_month_nutrition_status": {
                            "color": "black",
                            "value": "Normal weight for age"
                        },
                        "case_id": "71230690-c828-4863-b2c1-f61a75aed9d7",
                        "recorded_height": 0,
                        "fully_immunized": "No",
                        "person_name": "Name 4407",
                        "sex": "M",
                        "mother_name": "ममता बाई"
                    }
                ]
            }, cls=DjangoJSONEncoder)
        )
