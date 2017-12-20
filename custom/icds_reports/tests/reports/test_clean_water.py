from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors
from custom.icds_reports.reports.clean_water import get_clean_water_data_map, get_clean_water_data_chart, \
    get_clean_water_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestCleanWater(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_clean_water_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of AWCs with a source of clean drinking water",
                    "average": 58.0,
                    'extended_info': [
                        {
                            'indicator': 'Total number of AWCs with a source of clean drinking water:',
                            'value': "29"
                        },
                        {'indicator': '% of AWCs with a source of clean drinking water:', 'value': '58.00%'}
                    ]
                },
                "fills": {
                    "0%-25%": "#de2d26",
                    "25%-75%": "#fc9272",
                    "75%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "in_month": 17,
                        "all": 26,
                        'original_name': [],
                        "fillKey": "25%-75%"
                    },
                    "st2": {
                        "in_month": 12,
                        "all": 24,
                        'original_name': [],
                        "fillKey": "25%-75%"
                    }
                },
                "slug": "clean_water",
                "label": "Percent AWCs with Clean Drinking Water"
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_clean_water_data_map(
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
                    "info": "Percentage of AWCs with a source of clean drinking water",
                    "average": 65.38461538461539,
                    'extended_info': [
                        {
                            'indicator': 'Total number of AWCs with a source of clean drinking water:',
                            'value': "17"
                        },
                        {'indicator': '% of AWCs with a source of clean drinking water:', 'value': '65.38%'}
                    ]
                },
                "fills": {
                    "0%-25%": "#de2d26",
                    "25%-75%": "#fc9272",
                    "75%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    'block_map': {
                        'in_month': 17,
                        'original_name': ['b1', 'b2'],
                        'all': 26,
                        'fillKey': '25%-75%'
                    }
                },
                "slug": "clean_water",
                "label": "Percent AWCs with Clean Drinking Water"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_clean_water_data_chart(
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
                        "percent": 50.0
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 65.38461538461539
                    },
                    {
                        "loc_name": "st2",
                        "percent": 50.0
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
                                "y": 0.28,
                                "x": 1491004800000,
                                "in_month": 14
                            },
                            {
                                "y": 0.58,
                                "x": 1493596800000,
                                "in_month": 29
                            }
                        ],
                        "key": "% of AWCs with a source of clean drinking water"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 65.38461538461539
                    },
                    {
                        "loc_name": "st2",
                        "percent": 50.0
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_clean_water_sector_data(
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
                "info": "Percentage of AWCs with a source of clean drinking water",
                "tooltips_data": {
                    "s2": {
                        "in_month": 3,
                        "all": 7
                    },
                    "s1": {
                        "in_month": 5,
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
                                0.7142857142857143
                            ],
                            [
                                "s2",
                                0.42857142857142855
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
