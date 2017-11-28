from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors
from custom.icds_reports.reports.adolescent_girls import get_adolescent_girls_data_map, \
    get_adolescent_girls_data_chart, get_adolescent_girls_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestAdolescentGirls(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_adolescent_girls_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Total number of adolescent girls who are enrolled for ICDS services",
                    "average": 23.5,
                    "average_format": "number"
                },
                "fills": {
                    "Adolescent Girls": "#006fdf",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "valid": 22,
                        'original_name': [],
                        "fillKey": "Adolescent Girls"
                    },
                    "st2": {
                        "valid": 25,
                        'original_name': [],
                        "fillKey": "Adolescent Girls"
                    }
                },
                "slug": "adolescent_girls",
                "label": ""
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_adolescent_girls_data_map(
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
                    "info": "Total number of adolescent girls who are enrolled for ICDS services",
                    "average": 11.0,
                    "average_format": "number"
                },
                "fills": {
                    "Adolescent Girls": "#006fdf",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    'block_map': {
                        'valid': 22,
                        'original_name': ['b1', 'b2'],
                        'fillKey': 'Adolescent Girls'}
                },
                "slug": "adolescent_girls",
                "label": ""
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_adolescent_girls_data_chart(
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
                        "value": 25
                    },
                    {
                        "loc_name": "st1",
                        "value": 22
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "value": 25
                    },
                    {
                        "loc_name": "st1",
                        "value": 22
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
                                "y": 57.0,
                                "x": 1491004800000,
                                "all": 0
                            },
                            {
                                "y": 47.0,
                                "x": 1493596800000,
                                "all": 0
                            }
                        ],
                        "key": "Total number of adolescent girls who are enrolled for ICDS services"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st2",
                        "value": 25
                    },
                    {
                        "loc_name": "st1",
                        "value": 22
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_adolescent_girls_sector_data(
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
                "info": "Total number of adolescent girls who are enrolled for ICDS services",
                "tooltips_data": {
                    "s2": {
                        "valid": 6
                    },
                    "s1": {
                        "valid": 5
                    },
                },
                "chart_data": [
                    {
                        "color": "#006fdf",
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            [
                                "s1",
                                5
                            ],
                            [
                                "s2",
                                6
                            ]
                        ],
                        "key": "Number Of Girls"
                    }
                ],
                "format": "number"
            }
        )
