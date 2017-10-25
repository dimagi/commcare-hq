from django.test.utils import override_settings

from custom.icds_reports.reports.awc_daily_status import get_awc_daily_status_data_map, \
    get_awc_daily_status_data_chart, get_awc_daily_status_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
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
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of Angwanwadi Centers that were open yesterday.",
                    "average": 0.0,
                    "period": "Daily"
                },
                "fills": {
                    "0%-50%": "#de2d26",
                    "50%-75%": "#fc9272",
                    "75%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "in_day": 0,
                        "all": 8,
                        "fillKey": "0%-50%"
                    },
                    "st2": {
                        "in_day": 0,
                        "all": 11,
                        "fillKey": "0%-50%"
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
                "bottom_five": [],
                "top_five": [],
                "chart_data": [
                    {
                        "color": "#fee0d2",
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
                                "y": 0,
                                "x": 1495756800000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495843200000,
                                "all": 0
                            },
                            {
                                "y": 19,
                                "x": 1495929600000,
                                "all": 0
                            }
                        ],
                        "key": "Number of AWCs launched"
                    },
                    {
                        "color": "#006fdf",
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
                                "y": 0,
                                "x": 1495756800000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495843200000,
                                "all": 0
                            },
                            {
                                "y": 0,
                                "x": 1495929600000,
                                "all": 0
                            }
                        ],
                        "key": "Total AWCs open yesterday"
                    }
                ],
                "all_locations": []
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
                "info": "Percentage of Angwanwadi Centers that were open yesterday.",
                "tooltips_data": {
                    "s2": {
                        "in_day": 0,
                        "all": 1
                    },
                    "s1": {
                        "in_day": 0,
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
