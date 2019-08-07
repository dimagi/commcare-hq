from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.messages import awcs_launched_help_text
from custom.icds_reports.reports.awcs_covered import get_awcs_covered_data_map, get_awcs_covered_data_chart, \
    get_awcs_covered_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestAWCSCovered(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_awcs_covered_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": (
                        "{}<br /><br />"
                        'Number of AWCs launched: 21 <br />'
                        'Number of States launched: 3'.format(awcs_launched_help_text())
                    )
                },
                "fills": {
                    "Launched": MapColors.PINK,
                    "Not launched": MapColors.GREY,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'st4': {
                        'districts': 0,
                        'blocks': 0,
                        'awcs': 0,
                        'original_name': ['st4'],
                        'states': 0,
                        'supervisors': 0,
                        'fillKey': 'Not launched'},
                    'st5': {
                        'districts': 0,
                        'blocks': 0,
                        'awcs': 0,
                        'original_name': ['st5'],
                        'states': 0,
                        'supervisors': 0,
                        'fillKey': 'Not launched'
                    },
                    'st6': {
                        'districts': 0,
                        'blocks': 0,
                        'awcs': 0,
                        'original_name': ['st6'],
                        'states': 0,
                        'supervisors': 0,
                        'fillKey': 'Not launched'
                    },
                    'st7': {
                        'districts': 1,
                        'blocks': 1,
                        'awcs': 1,
                        'original_name': ['st7'],
                        'states': 1,
                        'supervisors': 1,
                        'fillKey': 'Launched'
                    },
                    'st1': {
                        'districts': 1,
                        'blocks': 2,
                        'awcs': 9,
                        'original_name': ['st1'],
                        'states': 1,
                        'supervisors': 4,
                        'fillKey': 'Launched'
                    },
                    'st2': {
                        'districts': 2,
                        'blocks': 2,
                        'awcs': 11,
                        'original_name': ['st2'],
                        'states': 1,
                        'supervisors': 4,
                        'fillKey': 'Launched'
                    },
                    'st3': {
                        'districts': 0,
                        'blocks': 0,
                        'awcs': 0,
                        'original_name': ['st3'],
                        'states': 0,
                        'supervisors': 0,
                        'fillKey': 'Not launched'
                    }
                },
                "slug": "awc_covered",
                "label": ""
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_awcs_covered_data_map(
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
                    "info": (
                        "{}<br /><br />"
                        'Number of AWCs launched: 9 <br />'
                        'Number of Blocks launched: 2'.format(awcs_launched_help_text())
                    )
                },
                "fills": {
                    "Launched": MapColors.PINK,
                    "Not launched": MapColors.GREY,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'block_map': {
                        'states': 1,
                        'blocks': 2,
                        'awcs': 9,
                        'original_name': ['b1', 'b2'],
                        'districts': 1,
                        'supervisors': 4,
                        'fillKey': 'Launched'
                    }
                },
                "slug": "awc_covered",
                "label": ""
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_awcs_covered_data_chart(
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
                    {'loc_name': 'st2', 'value': 11.0},
                    {'loc_name': 'st1', 'value': 9.0},
                    {'loc_name': 'st7', 'value': 1.0},
                    {'loc_name': 'st3', 'value': 0.0},
                    {'loc_name': 'st4', 'value': 0.0},
                ],
                "chart_data": [
                    {
                        "color": ChartColors.PINK,
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
                                "y": 21.0,
                                "x": 1491004800000,
                                "all": 0
                            },
                            {
                                "y": 21.0,
                                "x": 1493596800000,
                                "all": 0
                            }
                        ],
                        "key": "Number of AWCs Launched"
                    }
                ],
                "all_locations": [
                    {'loc_name': 'st2', 'value': 11.0},
                    {'loc_name': 'st1', 'value': 9.0},
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
            get_awcs_covered_sector_data(
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
                "info": (
                    "{}<br /><br />"
                    "Number of AWCs launched: 4 <br />"
                    "Number of Supervisors launched: 2".format(awcs_launched_help_text())
                ),
                "tooltips_data": {
                    "s2": {
                        "districts": 1,
                        "states": 1,
                        "supervisors": 1,
                        "blocks": 1,
                        "awcs": 2
                    }, 
                    "s1": {
                        "districts": 1,
                        "states": 1,
                        "supervisors": 1,
                        "blocks": 1,
                        "awcs": 2
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
                                2
                            ],
                            [
                                "s2",
                                2
                            ]
                        ],
                        "key": ""
                    }
                ],
                "format": "number"
            }
        )
