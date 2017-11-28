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
                    'aggregation_level': 1
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of AWCs with weighing scale for mother and child",
                    "average": 18.0
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
                        "all": 26.0,
                        'original_name': [],
                        "fillKey": "0%-25%"
                    },
                    "st2": {
                        "in_month": 4,
                        "all": 24.0,
                        'original_name': [],
                        "fillKey": "0%-25%"
                    }
                },
                "slug": "adult_weight_scale",
                "label": "Percent AWCs with Weighing Scale: Mother and Child"
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
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of AWCs with weighing scale for mother and child",
                    "average": 19.23076923076923
                },
                "fills": {
                    "0%-25%": "#de2d26",
                    "25%-75%": "#fc9272",
                    "75%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    'block_map': {
                        'in_month': 5,
                        'original_name': ['b1', 'b2'],
                        'all': 26,
                        'fillKey': '0%-25%'
                    }
                },
                "slug": "adult_weight_scale",
                "label": "Percent AWCs with Weighing Scale: Mother and Child"
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
                "location_type": "State",
                "bottom_five": [
                    {
                        "loc_name": "st1",
                        "percent": 19.23076923076923
                    },
                    {
                        "loc_name": "st2",
                        "percent": 16.666666666666668
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 19.23076923076923
                    },
                    {
                        "loc_name": "st2",
                        "percent": 16.666666666666668
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
                                "y": 0.06,
                                "x": 1491004800000,
                                "in_month": 3
                            },
                            {
                                "y": 0.18,
                                "x": 1493596800000,
                                "in_month": 9
                            }
                        ],
                        "key": "% of AWCs with a weighing scale for mother and child"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 19.23076923076923
                    },
                    {
                        "loc_name": "st2",
                        "percent": 16.666666666666668
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
                "info": "Percentage of AWCs with weighing scale for mother and child",
                "tooltips_data": {
                    "s2": {
                        "in_month": 1,
                        "all": 7
                    },
                    "s1": {
                        "in_month": 1,
                        "all": 7
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
                                0.14285714285714285
                            ],
                            [
                                "s2",
                                0.14285714285714285
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
