from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.early_initiation_breastfeeding import get_early_initiation_breastfeeding_map, \
    get_early_initiation_breastfeeding_chart, get_early_initiation_breastfeeding_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestEarlyInitiationBreastFeeding(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_early_initiation_breastfeeding_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": "Percentage of children who were put to the breast within one hour of birth."
                            "<br/><br/>Early initiation of breastfeeding ensure the newborn "
                            "recieves the 'first milk' rich in nutrients"
                            " and encourages exclusive breastfeeding practice",
                    "average": 57.142857142857146,
                    'extended_info': [
                        {'indicator': 'Total Number of Children born in the given month:', 'value': "7"},
                        {
                            'indicator': (
                                'Total Number of Children who were put to the breast within one hour of birth:'
                            ),
                            'value': "4"
                        },
                        {
                            'indicator': '% children who were put to the breast within one hour of birth:',
                            'value': '57.14%'
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
                        "in_month": 4,
                        "birth": 3,
                        'original_name': ["st1"],
                        "fillKey": "60%-100%"
                    },
                    "st2": {
                        "in_month": 3,
                        "birth": 1,
                        'original_name': ["st2"],
                        "fillKey": "20%-60%"
                    }
                },
                "slug": "early_initiation",
                "label": "Percent Early Initiation of Breastfeeding"
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_early_initiation_breastfeeding_map(
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
                    "info": "Percentage of children who were put to the breast within one hour of birth."
                            "<br/><br/>Early initiation of breastfeeding ensure the newborn "
                            "recieves the 'first milk' rich in nutrients"
                            " and encourages exclusive breastfeeding practice",
                    "average": 75.0,
                    'extended_info': [
                        {'indicator': 'Total Number of Children born in the given month:', 'value': "4"},
                        {
                            'indicator': (
                                'Total Number of Children who were put to the breast within one hour of birth:'
                            ),
                            'value': "3"
                        },
                        {
                            'indicator': '% children who were put to the breast within one hour of birth:',
                            'value': '75.00%'
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
                        'in_month': 4,
                        'original_name': ['b1', 'b2'],
                        'birth': 3,
                        'fillKey': '60%-100%'
                    }
                },
                "slug": "early_initiation",
                "label": "Percent Early Initiation of Breastfeeding"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_early_initiation_breastfeeding_chart(
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
                        "percent": 75.0
                    },
                    {
                        "loc_name": "st2",
                        "percent": 33.333333333333336
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 75.0
                    },
                    {
                        "loc_name": "st2",
                        "percent": 33.333333333333336
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
                                "birth": 0
                            },
                            {
                                "y": 0,
                                "x": 1488326400000,
                                "all": 0,
                                "birth": 0
                            },
                            {
                                "y": 0.25,
                                "x": 1491004800000,
                                "all": 8,
                                "birth": 2
                            },
                            {
                                "y": 0.5714285714285714,
                                "x": 1493596800000,
                                "all": 7,
                                "birth": 4
                            }
                        ],
                        "key": "% Early Initiation of Breastfeeding"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 75.0
                    },
                    {
                        "loc_name": "st2",
                        "percent": 33.333333333333336
                    }
                ]
            }

        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_early_initiation_breastfeeding_data(
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
                "info": "Percentage of children who were put to the breast within one hour of birth."
                        "<br/><br/>Early initiation of breastfeeding ensure the newborn recieves the 'first milk'"
                        " rich in nutrients and encourages exclusive breastfeeding practice",
                "tooltips_data": {
                    "s2": {
                        "in_month": 0,
                        "birth": 0
                    },
                    "s1": {
                        "in_month": 1,
                        "birth": 0
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
                                0.0
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
