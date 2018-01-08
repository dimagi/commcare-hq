from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.exclusive_breastfeeding import get_exclusive_breastfeeding_data_map, \
    get_exclusive_breastfeeding_data_chart, get_exclusive_breastfeeding_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestExclusiveBreastfeeding(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_exclusive_breastfeeding_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": "Percentage of infants 0-6 months of age who are fed exclusively "
                            "with breast milk. <br/><br/>An infant is exclusively breastfed "
                            "if they recieve only breastmilk with "
                            "no additional food, liquids (even water) "
                            "ensuring optimal nutrition and growth between 0 - 6 months",
                    "average": 56.0,
                    'extended_info': [
                        {
                            'indicator': 'Total number of children between ages 0 - 6 months:',
                            'value': "50"
                        },
                        {
                            'indicator': (
                                'Total number of children (0-6 months) exclusively breastfed in the given month:'
                            ),
                            'value': "28"
                        },
                        {
                            'indicator': '% children (0-6 months) exclusively breastfed in the given month:',
                            'value': '56.00%'
                        }
                    ]
                },
                "fills": {
                    "0%-20%": MapColors.RED,
                    "20%-60%": MapColors.ORANGE,
                    "60%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    "st1": {
                        "all": 26,
                        "children": 17,
                        'original_name': ["st1"],
                        "fillKey": "60%-100%"
                    },
                    "st2": {
                        "all": 24,
                        "children": 11,
                        'original_name': ["st2"],
                        "fillKey": "20%-60%"
                    }
                },
                "slug": "severe",
                "label": "Percent Exclusive Breastfeeding"
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_exclusive_breastfeeding_data_map(
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
                    "info": "Percentage of infants 0-6 months of age who are fed exclusively "
                            "with breast milk. <br/><br/>An infant is exclusively breastfed "
                            "if they recieve only breastmilk with "
                            "no additional food, liquids (even water) "
                            "ensuring optimal nutrition and growth between 0 - 6 months",
                    "average": 65.38461538461539,
                    'extended_info': [
                        {
                            'indicator': 'Total number of children between ages 0 - 6 months:',
                            'value': "26"
                        },
                        {
                            'indicator': (
                                'Total number of children (0-6 months) exclusively breastfed in the given month:'
                            ),
                            'value': "17"
                        },
                        {
                            'indicator': '% children (0-6 months) exclusively breastfed in the given month:',
                            'value': '65.38%'
                        }
                    ]
                },
                "fills": {
                    "0%-20%": MapColors.RED,
                    "20%-60%": MapColors.ORANGE,
                    "60%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'block_map': {
                        'all': 26,
                        'original_name': ['b1', 'b2'],
                        'children': 17,
                        'fillKey': '60%-100%'
                    }
                },
                "slug": "severe",
                "label": "Percent Exclusive Breastfeeding"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_exclusive_breastfeeding_data_chart(
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
                        "percent": 65.38461538461539
                    },
                    {
                        "loc_name": "st2",
                        "percent": 45.833333333333336
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 65.38461538461539
                    },
                    {
                        "loc_name": "st2",
                        "percent": 45.833333333333336
                    }
                ],
                "chart_data": [
                    {
                        "color": ChartColors.BLUE,
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            {
                                "y": 0,
                                "x": 1485907200000,
                                "all": 0,
                                "in_month": 0
                            },
                            {
                                "y": 0,
                                "x": 1488326400000,
                                "all": 0,
                                "in_month": 0
                            },
                            {
                                "y": 0.22413793103448276,
                                "x": 1491004800000,
                                "all": 58,
                                "in_month": 13
                            },
                            {
                                "y": 0.56,
                                "x": 1493596800000,
                                "all": 50,
                                "in_month": 28
                            }
                        ],
                        "key": "% children exclusively breastfed"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 65.38461538461539
                    },
                    {
                        "loc_name": "st2",
                        "percent": 45.833333333333336
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_exclusive_breastfeeding_sector_data(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'aggregation_level': 4
                },
                location_id='b1',
                loc_level='supervisor'
            ),
            {
                "info": "Percentage of infants 0-6 months of age who are fed exclusively with breast milk. "
                        "<br/><br/>An infant is exclusively breastfed if they recieve only breastmilk with"
                        " no additional food, liquids (even water) ensuring"
                        " optimal nutrition and growth between 0 - 6 months",
                "tooltips_data": {
                    "s2": {
                        "all": 13,
                        "children": 7
                    },
                    "s1": {
                        "all": 2,
                        "children": 0
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
                                0.0
                            ],
                            [
                                "s2",
                                0.5384615384615384
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
