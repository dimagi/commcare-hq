from __future__ import absolute_import

from django.test.utils import override_settings

from custom.icds_reports.reports.adult_weight_scale import get_adult_weight_scale_data_map, \
    get_adult_weight_scale_data_chart, get_adult_weight_scale_sector_data
from django.test import TestCase
from custom.icds_reports.const import ChartColors, MapColors


@override_settings(SERVER_ENVIRONMENT='icds')
class TestAdultWeightScale(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_adult_weight_scale_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": "Percentage of AWCs that reported having a weighing scale for mother and child",
                    "average": 30.09049773755656,
                    'extended_info': [
                        {
                            'indicator': 'Total number of AWCs with a weighing scale for mother and child:',
                            'value': "9"
                        },
                        {'indicator': '% of AWCs with a weighing scale for mother and child:', 'value': '30.00%'}
                    ]
                },
                "label": "Percentage of AWCs that reported having a weighing scale for mother and child",
                "data": {
                    "st1": {
                        "in_month": 5,
                        "original_name": ["st1"],
                        "all": 17,
                        "fillKey": "25%-75%"
                    },
                    "st2": {
                        "in_month": 4,
                        "original_name": ["st2"],
                        "all": 13,
                        "fillKey": "25%-75%"
                    }
                },
                "slug": "adult_weight_scale",
                "fills": {
                    "0%-25%": MapColors.RED,
                    "25%-75%": MapColors.ORANGE,
                    "75%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                }
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_adult_weight_scale_data_map(
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
                    "info": "Percentage of AWCs that reported having a weighing scale for mother and child",
                    "average": 29.41176470588235,
                    'extended_info': [
                        {
                            'indicator': 'Total number of AWCs with a weighing scale for mother and child:',
                            'value': "5"
                        },
                        {'indicator': '% of AWCs with a weighing scale for mother and child:', 'value': '29.41%'}
                    ]
                },
                "label": "Percentage of AWCs that reported having a weighing scale for mother and child",
                "data": {
                    "block_map": {
                        "in_month": 5,
                        "original_name": [
                            "b1",
                            "b2"
                        ],
                        "all": 17,
                        "fillKey": "25%-75%"
                    }
                },
                "slug": "adult_weight_scale",
                "fills": {
                    "0%-25%": MapColors.RED,
                    "25%-75%": MapColors.ORANGE,
                    "75%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                }
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_adult_weight_scale_data_chart(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "chart_data": [
                    {
                        "color": ChartColors.BLUE,
                        "values": [
                            {
                                "y": 0.0,
                                "x": 1485907200000,
                                "in_month": 0
                            },
                            {
                                "y": 0.0,
                                "x": 1488326400000,
                                "in_month": 0
                            },
                            {
                                "y": 0.21428571428571427,
                                "x": 1491004800000,
                                "in_month": 3
                            },
                            {
                                "y": 0.3,
                                "x": 1493596800000,
                                "in_month": 9
                            }
                        ],
                        "strokeWidth": 2,
                        "classed": "dashed",
                        "key": "Percentage of AWCs that reported having a weighing scale for mother and child"
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "percent": 30.76923076923077
                    },
                    {
                        "loc_name": "st1",
                        "percent": 29.41176470588235
                    }
                ],
                "location_type": "State",
                "all_locations": [
                    {
                        "loc_name": "st2",
                        "percent": 30.76923076923077
                    },
                    {
                        "loc_name": "st1",
                        "percent": 29.41176470588235
                    }
                ],
                "bottom_five": [
                    {
                        "loc_name": "st2",
                        "percent": 30.76923076923077
                    },
                    {
                        "loc_name": "st1",
                        "percent": 29.41176470588235
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_adult_weight_scale_sector_data(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'aggregation_level': 4
                },
                loc_level='supervisor',
                location_id='b1',
            ),
            {
                "info": "Percentage of AWCs that reported having a weighing scale for mother and child",
                "tooltips_data": {
                    "s2": {
                        "in_month": 1,
                        "all": 3
                    },
                    "s1": {
                        "in_month": 1,
                        "all": 5
                    }
                },
                "chart_data": [
                    {
                        "color": MapColors.BLUE,
                        "values": [
                            [
                                "s1",
                                0.2
                            ],
                            [
                                "s2",
                                0.3333333333333333
                            ]
                        ],
                        "strokeWidth": 2,
                        "classed": "dashed",
                        "key": ""
                    }
                ]
            }
        )
