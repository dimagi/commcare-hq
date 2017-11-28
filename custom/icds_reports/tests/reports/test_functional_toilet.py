
from __future__ import absolute_import
from django.test.utils import override_settings

from django.test import TestCase

from custom.icds_reports.const import ChartColors
from custom.icds_reports.reports.functional_toilet import get_functional_toilet_data_map, \
    get_functional_toilet_data_chart, get_functional_toilet_sector_data


@override_settings(SERVER_ENVIRONMENT='icds')
class TestFunctionalToilet(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_functional_toilet_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of AWCs with a functional toilet",
                    "average": 30.0
                },
                "fills": {
                    "0%-25%": "#de2d26",
                    "25%-75%": "#fc9272",
                    "75%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "in_month": 8,
                        "all": 26,
                        'original_name': [],
                        "fillKey": "25%-75%"
                    },
                    "st2": {
                        "in_month": 7,
                        "all": 24,
                        'original_name': [],
                        "fillKey": "25%-75%"
                    }
                },
                "slug": "functional_toilet",
                "label": "Percent AWCs with Functional Toilet"
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_functional_toilet_data_map(
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
                    "info": "Percentage of AWCs with a functional toilet",
                    "average": 30.76923076923077
                },
                "fills": {
                    "0%-25%": "#de2d26",
                    "25%-75%": "#fc9272",
                    "75%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    'block_map': {
                        'in_month': 8,
                        'original_name': ['b1', 'b2'],
                        'all': 26,
                        'fillKey': '25%-75%'
                    }
                },
                "slug": "functional_toilet",
                "label": "Percent AWCs with Functional Toilet"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_functional_toilet_data_chart(
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
                        "percent": 30.76923076923077
                    },
                    {
                        "loc_name": "st2",
                        "percent": 29.166666666666668
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 30.76923076923077
                    },
                    {
                        "loc_name": "st2",
                        "percent": 29.166666666666668
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
                                "y": 8.0,
                                "x": 1491004800000,
                                "in_month": 8
                            },
                            {
                                "y": 15.0,
                                "x": 1493596800000,
                                "in_month": 15
                            }
                        ],
                        "key": "% of AWCs with a functional toilet."
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 30.76923076923077
                    },
                    {
                        "loc_name": "st2",
                        "percent": 29.166666666666668
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_functional_toilet_sector_data(
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
                "info": "Percentage of AWCs with a functional toilet",
                "tooltips_data": {
                    "s2": {
                        "in_month": 0,
                        "all": 7
                    },
                    "s1": {
                        "in_month": 4,
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
                                0.5714285714285714
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
