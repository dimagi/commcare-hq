from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.awc_daily_status import get_awc_daily_status_data_map, \
    get_awc_daily_status_data_chart, get_awc_daily_status_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds-new')
class TestAWCDailyStatus(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_awc_daily_status_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 28),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": "Of the total number of AWCs, the percentage of AWCs that were open yesterday.",
                    "average": 0.0,
                    "period": "Daily",
                    'extended_info': [
                        {'indicator': 'Total number of AWCs that were open yesterday:', 'value': "0"},
                        {'indicator': 'Total number of AWCs that have been launched:', 'value': "21"},
                        {'indicator': '% of AWCs open yesterday:', 'value': '0.00%'}
                    ]
                },
                "fills": {
                    "0%-50%": MapColors.RED,
                    "50%-75%": MapColors.ORANGE,
                    "75%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'st7': {'in_day': 0, 'all': 1, 'original_name': ['st7'], 'fillKey': '0%-50%'},
                    'st1': {'in_day': 0, 'all': 9, 'original_name': ['st1'], 'fillKey': '0%-50%'},
                    'st2': {'in_day': 0, 'all': 11, 'original_name': ['st2'], 'fillKey': '0%-50%'}
                },
                "slug": "awc_daily_statuses",
                "label": "Percent AWCs Open Yesterday"
            }
        )

    def test_map_data_if_aggregation_script_fail(self):
        self.assertDictEqual(
            get_awc_daily_status_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 29),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": "Of the total number of AWCs, the percentage of AWCs that were open yesterday.",
                    "average": 0.0,
                    "extended_info": [
                        {
                            "indicator": "Total number of AWCs that were open yesterday:",
                            "value": "0"
                        },
                        {
                            "indicator": "Total number of AWCs that have been launched:",
                            "value": "21"
                        },
                        {
                            "indicator": "% of AWCs open yesterday:",
                            "value": "0.00%"
                        }
                    ],
                    "period": "Daily"
                },
                "label": "Percent AWCs Open Yesterday",
                "data": {
                    'st7': {'in_day': 0, 'all': 1, 'original_name': ['st7'], 'fillKey': '0%-50%'},
                    'st1': {'in_day': 0, 'all': 9, 'original_name': ['st1'], 'fillKey': '0%-50%'},
                    'st2': {'in_day': 0, 'all': 11, 'original_name': ['st2'], 'fillKey': '0%-50%'}
                },
                "slug": "awc_daily_statuses",
                "fills": {
                    "0%-50%": MapColors.RED,
                    "50%-75%": MapColors.ORANGE,
                    "75%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                }
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_awc_daily_status_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 28),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'aggregation_level': 4
                },
                loc_level='block',
            ),
            {
                "rightLegend": {
                    "info": "Of the total number of AWCs, the percentage of AWCs that were open yesterday.",
                    "average": 0.0,
                    "period": "Daily",
                    'extended_info': [
                        {'indicator': 'Total number of AWCs that were open yesterday:', 'value': "0"},
                        {'indicator': 'Total number of AWCs that have been launched:', 'value': "9"},
                        {'indicator': '% of AWCs open yesterday:', 'value': '0.00%'}
                    ]
                },
                "fills": {
                    "0%-50%": MapColors.RED,
                    "50%-75%": MapColors.ORANGE,
                    "75%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                },
                'data': {
                    'block_map': {
                        'in_day': 0,
                        'all': 9,
                        'original_name': ['b1', 'b2'],
                        'fillKey': '0%-50%'
                    }
                },
                "slug": "awc_daily_statuses",
                "label": "Percent AWCs Open Yesterday"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_awc_daily_status_data_chart(
                'icds-cas',
                config={
                    'month': (2017, 5, 28),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "location_type": "State",
                "chart_data": [
                    {
                        "color": ChartColors.PINK,
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            {
                                "y": 0,
                                "x": 1493337600000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493424000000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493510400000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493596800000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493683200000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493769600000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493856000000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493942400000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494028800000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494115200000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494201600000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494288000000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494374400000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494460800000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494547200000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494633600000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494720000000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494806400000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494892800000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494979200000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495065600000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495152000000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495238400000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495324800000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495411200000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495497600000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495584000000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495670400000,
                                "all": 0
                            },
                            {
                                "y": 21,
                                "x": 1495756800000,
                                "all": 0
                            },
                            {
                                "y": 21,
                                "x": 1495843200000,
                                "all": 0
                            },
                            {
                                "y": 21,
                                "x": 1495929600000,
                                "all": 0
                            }
                        ],
                        "key": "Number of AWCs launched"
                    },
                    {
                        "color": ChartColors.BLUE,
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            {
                                "y": 0,
                                "x": 1493337600000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493424000000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493510400000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493596800000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493683200000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493769600000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493856000000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1493942400000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494028800000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494115200000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494201600000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494288000000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494374400000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494460800000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494547200000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494633600000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494720000000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494806400000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494892800000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1494979200000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495065600000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495152000000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495238400000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495324800000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495411200000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495497600000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495584000000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495670400000,
                                "all": 0
                            },
                            {
                                "y": 38,
                                "x": 1495756800000,
                                "all": 0
                            },
                            {
                                "y": 34,
                                "x": 1495843200000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495929600000,
                                "all": 0
                            }
                        ],
                        "key": "Total AWCs open"
                    }
                ],
                "top_five": [
                    {'loc_name': 'st1', 'percent': 0.0},
                    {'loc_name': 'st2', 'percent': 0.0},
                    {'loc_name': 'st7', 'percent': 0.0},
                ],
                "all_locations": [
                    {'loc_name': 'st1', 'percent': 0.0},
                    {'loc_name': 'st2', 'percent': 0.0},
                    {'loc_name': 'st7', 'percent': 0.0},
                ],
                "bottom_five": [
                    {'loc_name': 'st1', 'percent': 0.0},
                    {'loc_name': 'st2', 'percent': 0.0},
                    {'loc_name': 'st7', 'percent': 0.0},
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_awc_daily_status_sector_data(
                'icds-cas',
                config={
                    'month': (2017, 5, 28),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'aggregation_level': 4
                },
                location_id='b1',
                loc_level='supervisor'
            ),
            {
                "info": "Of the total number of AWCs, the percentage of AWCs that were open yesterday.",
                "tooltips_data": {
                    "s2": {
                        "in_day": 0,
                        "all": 2
                    },
                    "s1": {
                        "in_day": 0,
                        "all": 2
                    }
                },
                "chart_data": [
                    {
                        "color": MapColors.BLUE,
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            ["s1", 0.0],
                            ["s2", 0.0]
                        ],
                        "key": ""
                    }
                ]
            }
        )

    def test_sector_data_if_aggregation_script_fail(self):
        self.assertDictEqual(
            get_awc_daily_status_sector_data(
                'icds-cas',
                config={
                    'month': (2017, 5, 29),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'aggregation_level': 4
                },
                location_id='b1',
                loc_level='supervisor'
            ),
            {
                "info": "Of the total number of AWCs, the percentage of AWCs that were open yesterday.",
                "tooltips_data": {
                    "s2": {
                        "in_day": 0,
                        "all": 2
                    },
                    "s1": {
                        "in_day": 0,
                        "all": 2
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
                                0.0
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
