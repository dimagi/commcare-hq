from __future__ import absolute_import

from django.test.utils import override_settings

from custom.icds_reports.reports.infants_weight_scale import get_infants_weight_scale_data_map, \
    get_infants_weight_scale_data_chart, get_infants_weight_scale_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestInfantsWeightScale(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_infants_weight_scale_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": "Percentage of AWCs that reported having a weighing scale for infants",
                    "average": 80.0,
                    'extended_info': [
                        {'indicator': 'Total number of AWCs with a weighing scale for infants:', 'value': "24"},
                        {'indicator': '% of AWCs with a weighing scale for infants:', 'value': '80.00%'}
                    ]
                },
                "label": "Percentage of AWCs that reported having a weighing scale for infants",
                "data": {
                    "st1": {
                        "in_month": 13,
                        "original_name": ["st1"],
                        "all": 17,
                        "fillKey": "75%-100%"
                    },
                    "st2": {
                        "in_month": 11,
                        "original_name": ["st2"],
                        "all": 13,
                        "fillKey": "75%-100%"
                    }
                },
                "slug": "infants_weight_scale",
                "fills": {
                    "0%-25%": "#de2d26",
                    "25%-75%": "#fc9272",
                    "75%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                }
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_infants_weight_scale_data_map(
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
                    "info": "Percentage of AWCs that reported having a weighing scale for infants",
                    "average": 76.47058823529412,
                    'extended_info': [
                        {'indicator': 'Total number of AWCs with a weighing scale for infants:', 'value': "13"},
                        {'indicator': '% of AWCs with a weighing scale for infants:', 'value': '76.47%'}
                    ]
                },
                "label": "Percentage of AWCs that reported having a weighing scale for infants",
                "data": {
                    "block_map": {
                        "in_month": 13,
                        "original_name": [
                            "b1",
                            "b2"
                        ],
                        "all": 17,
                        "fillKey": "75%-100%"
                    }
                },
                "slug": "infants_weight_scale",
                "fills": {
                    "0%-25%": "#de2d26",
                    "25%-75%": "#fc9272",
                    "75%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                }
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_infants_weight_scale_data_chart(
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
                        "percent": 1300.0
                    },
                    {
                        "loc_name": "st2",
                        "percent": 1100.0
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 1300.0
                    },
                    {
                        "loc_name": "st2",
                        "percent": 1100.0
                    }
                ],
                "chart_data": [
                    {
                        "color": "#005ebd",
                        "classed": "dashed",
                        "strokeWidth": 2,
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
                                "y": 5.0,
                                "x": 1491004800000,
                                "in_month": 10
                            },
                            {
                                "y": 12.0,
                                "x": 1493596800000,
                                "in_month": 24
                            }
                        ],
                        "key": "Percentage of AWCs that reported having a weighing scale for infants"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 1300.0
                    },
                    {
                        "loc_name": "st2",
                        "percent": 1100.0
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_infants_weight_scale_sector_data(
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
                "info": "Percentage of AWCs that reported having a weighing scale for infants",
                "tooltips_data": {
                    "s2": {
                        "in_month": 3,
                        "all": 1
                    },
                    "s1": {
                        "in_month": 4,
                        "all": 1
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
                                4.0
                            ],
                            [
                                "s2",
                                3.0
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
