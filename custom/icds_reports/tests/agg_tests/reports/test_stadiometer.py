from django.test.utils import override_settings

from custom.icds_reports.messages import awcs_reported_stadiometer_text
from custom.icds_reports.reports.stadiometer import get_stadiometer_data_map, get_stadiometer_data_chart, \
    get_stadiometer_sector_data
from django.test import TestCase
from custom.icds_reports.const import ChartColors, MapColors


@override_settings(SERVER_ENVIRONMENT='icds')
class TestStadiometer(TestCase):

    def test_map_data(self):
        print(get_stadiometer_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ))
        assert False
        self.assertDictEqual(
            get_stadiometer_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": awcs_reported_stadiometer_text(),
                    "average": 3.3333333333333335,
                    'extended_info': [
                        {
                            'indicator': 'Total number of AWCs with a Stadiometer:',
                            'value': "1"
                        },
                        {'indicator': '% of AWCs with a Stadiometer:', 'value': '3.33%'}
                    ]
                },
                "label": "Percentage of AWCs that reported having a Stadiometer",
                "data": {
                    'st4': {'in_month': 0, 'original_name': ['st4'], 'all': 0, 'fillKey': '0%-25%'},
                    'st5': {'in_month': 0, 'original_name': ['st5'], 'all': 0, 'fillKey': '0%-25%'},
                    'st6': {'in_month': 0, 'original_name': ['st6'], 'all': 0, 'fillKey': '0%-25%'},
                    'st7': {'in_month': 0, 'original_name': ['st7'], 'all': 0, 'fillKey': '0%-25%'},
                    'st1': {'in_month': 1, 'original_name': ['st1'], 'all': 17, 'fillKey': '0%-25%'},
                    'st2': {'in_month': 0, 'original_name': ['st2'], 'all': 13, 'fillKey': '0%-25%'},
                    'st3': {'in_month': 0, 'original_name': ['st3'], 'all': 0, 'fillKey': '0%-25%'}
                },
                "slug": "stadiometer",
                "fills": {
                    "0%-25%": MapColors.RED,
                    "25%-75%": MapColors.ORANGE,
                    "75%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                }
            }
        )

    def test_map_name_is_different_data(self):
        print(get_stadiometer_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'aggregation_level': 3
                },
                loc_level='block',
            ))
        self.assertDictEqual(
            get_stadiometer_data_map(
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
                    "info": awcs_reported_stadiometer_text(),
                    "average": 5.882352941176471,
                    'extended_info': [
                        {
                            'indicator': 'Total number of AWCs with a Stadiometer:',
                            'value': "1"
                        },
                        {'indicator': '% of AWCs with a Stadiometer:', 'value': '5.88%'}
                    ]
                },
                "label": "Percentage of AWCs that reported having a Stadiometer",
                "data": {
                    "block_map": {
                        "in_month": 1,
                        "original_name": [
                            "b1",
                            "b2"
                        ],
                        "all": 17,
                        "fillKey": "0%-25%"
                    }
                },
                "slug": "stadiometer",
                "fills": {
                    "0%-25%": MapColors.RED,
                    "25%-75%": MapColors.ORANGE,
                    "75%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                }
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_stadiometer_data_chart(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "chart_data": [
                    {
                        "color": ChartColors.BLUE,
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
                                "y": 0.07142857142857142,
                                "x": 1491004800000,
                                "in_month": 1
                            },
                            {
                                "y": 0.03333333333333333,
                                "x": 1493596800000,
                                "in_month": 1
                            }
                        ],
                        "strokeWidth": 2,
                        "classed": "dashed",
                        "key": "Percentage of AWCs that reported having a Stadiometer"
                    }
                ],
                "top_five": [
                    {'loc_name': 'st1', 'percent': 5.882352941176471},
                    {'loc_name': 'st2', 'percent': 0.0},
                    {'loc_name': 'st3', 'percent': 0.0},
                    {'loc_name': 'st4', 'percent': 0.0},
                    {'loc_name': 'st5', 'percent': 0.0},
                ],
                "location_type": "State",
                "all_locations": [
                    {'loc_name': 'st1', 'percent': 5.882352941176471},
                    {'loc_name': 'st2', 'percent': 0.0},
                    {'loc_name': 'st3', 'percent': 0.0},
                    {'loc_name': 'st4', 'percent': 0.0},
                    {'loc_name': 'st5', 'percent': 0.0},
                    {'loc_name': 'st6', 'percent': 0.0},
                    {'loc_name': 'st7', 'percent': 0.0},
                ],
                "bottom_five": [
                    {'loc_name': 'st3', 'percent': 0.0},
                    {'loc_name': 'st4', 'percent': 0.0},
                    {'loc_name': 'st5', 'percent': 0.0},
                    {'loc_name': 'st6', 'percent': 0.0},
                    {'loc_name': 'st7', 'percent': 0.0},
                ]
            }
        )

    def test_sector_data(self):
        print(get_stadiometer_sector_data(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b2',
                    'aggregation_level': 4
                },
                location_id='b1',
                loc_level='supervisor'
            ))
        assert False
        self.assertDictEqual(
            get_stadiometer_sector_data(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b2',
                    'aggregation_level': 4
                },
                location_id='b1',
                loc_level='supervisor'
            ),
            {
                "info": awcs_reported_stadiometer_text(),
                "tooltips_data": {
                    "s2": {
                        "in_month": 0,
                        "all": 3
                    },
                    "s1": {
                        "in_month": 0,
                        "all": 5
                    }
                },
                "chart_data": [
                    {
                        "color": MapColors.BLUE,
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
                        "strokeWidth": 2,
                        "classed": "dashed",
                        "key": ""
                    }
                ]
            }
        )
