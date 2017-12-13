from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors
from custom.icds_reports.reports.children_initiated_data import get_children_initiated_data_map, \
    get_children_initiated_data_chart, get_children_initiated_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestChildrenInitiated(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_children_initiated_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of children between 6 - 8 months"
                            " given timely introduction to solid, semi-solid or soft food.",
                    "average": 85.0,
                    'extended_info': [
                        {'indicator': 'Total number of children between age 6 - 8 months:', 'value': 40},
                        {
                            'indicator': (
                                'Total number of children (6-8 months) given timely introduction '
                                'to sold or semi-solid food in the given month:'
                            ),
                            'value': 34
                        },
                        {
                            'indicator': (
                                '% children (6-8 months) given timely introduction '
                                'to solid or semi-solid food in the given month:'
                            ),
                            'value': '85.00%'
                        }
                    ]
                },
                "fills": {
                    "0%-20%": "#de2d26",
                    "20%-60%": "#fc9272",
                    "60%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "all": 17,
                        "children": 14,
                        'original_name': [],
                        "fillKey": "60%-100%"
                    },
                    "st2": {
                        "all": 23,
                        "children": 20,
                        'original_name': [],
                        "fillKey": "60%-100%"
                    }
                },
                "slug": "severe",
                "label": "Percent Children (6-8 months) initiated Complementary Feeding"
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_children_initiated_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'aggregation_level': 3
                },
                loc_level='block',
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of children between 6 - 8 months"
                            " given timely introduction to solid, semi-solid or soft food.",
                    "average": 82.3529411764706,
                    'extended_info': [
                        {'indicator': 'Total number of children between age 6 - 8 months:', 'value': 17},
                        {
                            'indicator': (
                                'Total number of children (6-8 months) given timely introduction '
                                'to sold or semi-solid food in the given month:'
                            ),
                            'value': 14
                        },
                        {
                            'indicator': (
                                '% children (6-8 months) given timely introduction '
                                'to solid or semi-solid food in the given month:'
                            ),
                            'value': '82.35%'
                        }
                    ]
                },
                "fills": {
                    "0%-20%": "#de2d26",
                    "20%-60%": "#fc9272",
                    "60%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    'block_map': {
                        'all': 17,
                        'original_name': ['b1', 'b2'],
                        'children': 14,
                        'fillKey': '60%-100%'
                    }
                },
                "slug": "severe",
                "label": "Percent Children (6-8 months) initiated Complementary Feeding"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_children_initiated_data_chart(
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
                        "loc_name": "st2",
                        "percent": 86.95652173913044
                    },
                    {
                        "loc_name": "st1",
                        "percent": 82.3529411764706
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "percent": 86.95652173913044
                    },
                    {
                        "loc_name": "st1",
                        "percent": 82.3529411764706
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
                                "y": 0.34375,
                                "x": 1491004800000,
                                "all": 32,
                                "in_month": 11
                            },
                            {
                                "y": 0.85,
                                "x": 1493596800000,
                                "all": 40,
                                "in_month": 34
                            }
                        ],
                        "key": "% Children began complementary feeding"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st2",
                        "percent": 86.95652173913044
                    },
                    {
                        "loc_name": "st1",
                        "percent": 82.3529411764706
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_children_initiated_sector_data(
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
                "info": "Percentage of children between 6 - 8 months "
                        "given timely introduction to solid, semi-solid or soft food.",
                "tooltips_data": {
                    "s2": {
                        "all": 7,
                        "children": 6
                    },
                    "s1": {
                        "all": 3,
                        "children": 3
                    }
                },
                "chart_data": [
                    {
                        "color": "#006fdf",
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            [
                                "s1",
                                1.0
                            ],
                            [
                                "s2",
                                0.8571428571428571
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
