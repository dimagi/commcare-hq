from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
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
            ),
            {
                "rightLegend": {
                    "info": "Total number of adolescent girls who are enrolled for ICDS services",
                    "average": 23.5,
                    "average_format": "number",
                    'extended_info': [
                        {
                            'indicator': (
                                'Number of adolescent girls (11 - 18 years) who are enrolled for ICDS services:'
                            ),
                            'value': "47"
                        },
                        {
                            'indicator': 'Total number of adolescent girls (11 - 18 years) who are registered:',
                            'value': "47"
                        },
                        {
                            'indicator': (
                                'Percentage of registered adolescent girls (11 - 18 years) '
                                'who are enrolled for ICDS services:'
                            ),
                            'value': '100.00%'
                        }
                    ]
                },
                "fills": {
                    "Adolescent Girls": MapColors.BLUE,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    "st1": {
                        "valid": 22,
                        "all": 22,
                        'original_name': ["st1"],
                        "fillKey": "Adolescent Girls"
                    },
                    "st2": {
                        "valid": 25,
                        "all": 25,
                        'original_name': ["st2"],
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
            ),
            {
                "rightLegend": {
                    "info": "Total number of adolescent girls who are enrolled for ICDS services",
                    "average": 11.0,
                    "average_format": "number",
                    'extended_info': [
                        {
                            'indicator': (
                                'Number of adolescent girls (11 - 18 years) who are enrolled for ICDS services:'
                            ),
                            'value': "22"
                        },
                        {
                            'indicator': 'Total number of adolescent girls (11 - 18 years) who are registered:',
                            'value': "22"
                        },
                        {
                            'indicator': (
                                'Percentage of registered adolescent girls (11 - 18 years) '
                                'who are enrolled for ICDS services:'
                            ),
                            'value': '100.00%'
                        }
                    ]
                },
                "fills": {
                    "Adolescent Girls": MapColors.BLUE,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'block_map': {
                        'valid': 22,
                        'all': 22,
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
                                "y": 0,
                                "x": 1485907200000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1488326400000,
                                "all": 0
                            },
                            {
                                "y": 57,
                                "x": 1491004800000,
                                "all": 57
                            },
                            {
                                "y": 47,
                                "x": 1493596800000,
                                "all": 47
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
                        "all": 6,
                        "valid": 6
                    },
                    "s1": {
                        "valid": 5,
                        "all": 5
                    },
                },
                "chart_data": [
                    {
                        "color": MapColors.BLUE,
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
