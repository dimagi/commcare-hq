from __future__ import absolute_import

from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.messages import percent_lactating_women_enrolled_help_text
from custom.icds_reports.reports.lactating_enrolled_women import get_lactating_enrolled_women_data_map, \
    get_lactating_enrolled_women_sector_data, get_lactating_enrolled_data_chart
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds-new')
class TestLactatingEnrolledWomen(TestCase):

    def test_chart_data(self):
        self.assertDictEqual(
            get_lactating_enrolled_data_chart(
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
                    {'loc_name': 'st7', 'value': 1.0},
                    {'loc_name': 'st3', 'value': 0.0},
                    {'loc_name': 'st4', 'value': 0.0},
                    {'loc_name': 'st5', 'value': 0.0},
                    {'loc_name': 'st6', 'value': 0.0},
                ],
                "top_five": [
                    {'loc_name': 'st1', 'value': 87.0},
                    {'loc_name': 'st2', 'value': 79.0},
                    {'loc_name': 'st7', 'value': 1.0},
                    {'loc_name': 'st3', 'value': 0.0},
                    {'loc_name': 'st4', 'value': 0.0},
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
                                "y": 160,
                                "x": 1491004800000,
                                "all": 160
                            },
                            {
                                "y": 167,
                                "x": 1493596800000,
                                "all": 167
                            }
                        ],
                        "key": "Total number of lactating women who are enrolled for Anganwadi Services"
                    }
                ],
                "all_locations": [
                    {'loc_name': 'st1', 'value': 87.0},
                    {'loc_name': 'st2', 'value': 79.0},
                    {'loc_name': 'st7', 'value': 1.0},
                    {'loc_name': 'st3', 'value': 0.0},
                    {'loc_name': 'st4', 'value': 0.0},
                    {'loc_name': 'st5', 'value': 0.0},
                    {'loc_name': 'st6', 'value': 0.0},
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_lactating_enrolled_women_sector_data(
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
                "info": percent_lactating_women_enrolled_help_text(),
                "tooltips_data": {
                    "s2": {
                        "valid": 24,
                        "all": 24
                    },
                    "s1": {
                        "valid": 19,
                        "all": 19
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
                                19
                            ],
                            [
                                "s2",
                                24
                            ]
                        ],
                        "key": ""
                    }
                ],
                "format": "number"
            }
        )

    def test_map_data(self):
        self.assertDictEqual(
            get_lactating_enrolled_women_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": percent_lactating_women_enrolled_help_text(),
                    "average": '100.00',
                    'extended_info': [
                        {
                            'indicator': 'Number of lactating women who are enrolled for Anganwadi Services:',
                            'value': "167"
                        },
                        {'indicator': 'Total number of lactating women who are registered:', 'value': "167"},
                        {
                            'indicator': (
                                'Percentage of registered lactating women who are enrolled for Anganwadi Services:'
                            ),
                            'value': '100.00%'
                        }
                    ]
                },
                "fills": {
                    "Women": MapColors.BLUE,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'st4': {'all': 0, 'valid': 0, 'original_name': ['st4'], 'fillKey': 'Women'},
                    'st5': {'all': 0, 'valid': 0, 'original_name': ['st5'], 'fillKey': 'Women'},
                    'st6': {'all': 0, 'valid': 0, 'original_name': ['st6'], 'fillKey': 'Women'},
                    'st7': {'all': 1, 'valid': 1, 'original_name': ['st7'], 'fillKey': 'Women'},
                    'st1': {'all': 87, 'valid': 87, 'original_name': ['st1'], 'fillKey': 'Women'},
                    'st2': {'all': 79, 'valid': 79, 'original_name': ['st2'], 'fillKey': 'Women'},
                    'st3': {'all': 0, 'valid': 0, 'original_name': ['st3'], 'fillKey': 'Women'}
                },
                "slug": "lactating_enrolled_women",
                "label": ""
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_lactating_enrolled_women_data_map(
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
                    "info": percent_lactating_women_enrolled_help_text(),
                    "average": '100.00',
                    'extended_info': [
                        {
                            'indicator': 'Number of lactating women who are enrolled for Anganwadi Services:',
                            'value': "87"
                        },
                        {'indicator': 'Total number of lactating women who are registered:', 'value': "87"},
                        {
                            'indicator': (
                                'Percentage of registered lactating women who are enrolled for Anganwadi Services:'
                            ),
                            'value': '100.00%'
                        }
                    ]
                },
                "fills": {
                    "Women": MapColors.BLUE,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'block_map': {
                        'valid': 87,
                        'all': 87,
                        'original_name': ['b1', 'b2'],
                        'fillKey': 'Women'
                    }
                },
                "slug": "lactating_enrolled_women",
                "label": ""
            }
        )
