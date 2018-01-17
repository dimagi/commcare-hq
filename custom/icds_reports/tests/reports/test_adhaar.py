from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.adhaar import get_adhaar_data_map, get_adhaar_data_chart, get_adhaar_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestAdhaar(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_adhaar_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": "Percentage of individuals registered using CAS "
                            "whose Aadhaar identification has been captured",
                    "average": 24.764682812040398,
                    'extended_info': [
                        {
                            'indicator': 'Total number of ICDS beneficiaries whose Aadhaar has been captured:',
                            'value': "122"
                        },
                        {
                            'indicator': '% of ICDS beneficiaries whose Aadhaar has been captured:',
                            'value': '24.45%'
                        }
                    ]
                },
                "fills": {
                    "0%-25%": MapColors.RED,
                    "25%-50%": MapColors.ORANGE,
                    "50%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    "st1": {
                        "in_month": 59,
                        "all": 217,
                        'original_name': ["st1"],
                        "fillKey": "25%-50%"
                    },
                    "st2": {
                        "in_month": 63,
                        "all": 282,
                        'original_name': ["st2"],
                        "fillKey": "0%-25%"
                    }
                },
                "slug": "adhaar",
                "label": "Percent Aadhaar-seeded Beneficiaries"
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_adhaar_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'aggregation_level': 3
                },
                loc_level='block',
            ),
            {
                "rightLegend": {
                    "info": "Percentage of individuals registered using CAS "
                            "whose Aadhaar identification has been captured",
                    "average": 27.1889400921659,
                    'extended_info': [
                        {
                            'indicator': 'Total number of ICDS beneficiaries whose Aadhaar has been captured:',
                            'value': "59"
                        },
                        {
                            'indicator': '% of ICDS beneficiaries whose Aadhaar has been captured:',
                            'value': '27.19%'
                        }
                    ]
                },
                "fills": {
                    "0%-25%": MapColors.RED,
                    "25%-50%": MapColors.ORANGE,
                    "50%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'block_map': {
                        'in_month': 59,
                        'original_name': ['b1', 'b2'],
                        'all': 217,
                        'fillKey': '25%-50%'
                    }
                },
                "slug": "adhaar",
                "label": "Percent Aadhaar-seeded Beneficiaries"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_adhaar_data_chart(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "location_type": "State",
                "bottom_five": [
                    {
                        "loc_name": "st1",
                        "percent": 27.1889400921659
                    },
                    {
                        "loc_name": "st2",
                        "percent": 22.340425531914892
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 27.1889400921659
                    },
                    {
                        "loc_name": "st2",
                        "percent": 22.340425531914892
                    }
                ],
                "chart_data": [
                    {
                        "color": ChartColors.BLUE,
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            {
                                "y": 0.0,
                                "x": 1485907200000,
                                "all": 0
                            },
                            {
                                "y": 0.0,
                                "x": 1488326400000,
                                "all": 0
                            },
                            {
                                "y": 0.22273781902552203,
                                "x": 1491004800000,
                                "all": 431
                            },
                            {
                                "y": 0.24448897795591182,
                                "x": 1493596800000,
                                "all": 499
                            }
                        ],
                        "key": "Percentage of beneficiaries with Aadhaar numbers"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 27.1889400921659
                    },
                    {
                        "loc_name": "st2",
                        "percent": 22.340425531914892
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_adhaar_sector_data(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'aggregation_level': 4
                },
                loc_level='supervisor',
                location_id='b1'
            ),
            {
                "info": "Percentage of individuals registered using "
                        "CAS whose Aadhaar identification has been captured",
                "tooltips_data": {
                    "s2": {
                        "in_month": 15,
                        "all": 62
                    },
                    "s1": {
                        "in_month": 22,
                        "all": 41
                    }
                },
                "chart_data": [
                    {
                        "color": MapColors.BLUE,
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            [
                                "s1",
                                0.5365853658536586
                            ],
                            [
                                "s2",
                                0.24193548387096775
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
