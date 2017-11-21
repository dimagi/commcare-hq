from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors
from custom.icds_reports.reports.adult_weight_scale import get_adult_weight_scale_data_map, \
    get_adult_weight_scale_data_chart, get_adult_weight_scale_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestAdultWeightScale(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_adult_weight_scale_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 5
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of AWCs that reported having a weighing scale for mother and child",
                    "average": 45.0
                },
                "fills": {
                    "0%-25%": "#de2d26",
                    "25%-75%": "#fc9272",
                    "75%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "in_month": 5,
                        "all": 9.0,
                        "fillKey": "25%-75%"
                    },
                    "st2": {
                        "in_month": 4,
                        "all": 11.0,
                        "fillKey": "25%-75%"
                    }
                },
                "slug": "adult_weight_scale",
                "label": "Percentage of AWCs that reported having a weighing scale for mother and child"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_adult_weight_scale_data_chart(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 5
                },
                loc_level='state'
            ),
            {
                "location_type": "State",
                "bottom_five": [
                    {
                        "loc_name": "st1",
                        "percent": 55.55555555555556
                    },
                    {
                        "loc_name": "st2",
                        "percent": 36.36363636363637
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 55.55555555555556
                    },
                    {
                        "loc_name": "st2",
                        "percent": 36.36363636363637
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
                                "in_month": 0
                            },
                            {
                                "y": 0.0,
                                "x": 1488326400000,
                                "in_month": 0
                            },
                            {
                                "y": 0.08333333333333333,
                                "x": 1491004800000,
                                "in_month": 3
                            },
                            {
                                "y": 0.45,
                                "x": 1493596800000,
                                "in_month": 9
                            }
                        ],
                        "key": "Percentage of AWCs that reported having a weighing scale for mother and child"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 55.55555555555556
                    },
                    {
                        "loc_name": "st2",
                        "percent": 36.36363636363637
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
                    'aggregation_level': 5
                },
                loc_level='supervisor',
                location_id='b1',
            ),
            {
                "info": "Percentage of AWCs that reported having a weighing scale for mother and child",
                "tooltips_data": {
                    "s2": {
                        "in_month": 1,
                        "all": 4
                    },
                    "s1": {
                        "in_month": 1,
                        "all": 2
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
                                0.5
                            ],
                            [
                                "s2",
                                0.25
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
