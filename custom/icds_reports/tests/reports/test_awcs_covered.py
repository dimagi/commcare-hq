from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors
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
                        'Total AWCs that have launched ICDS CAS <br />'
                        'Number of AWCs launched: 19 <br />'
                        'Number of States launched: 2'
                    )
                },
                "fills": {
                    "Launched": "#fee0d2",
                    "Not launched": "#9D9D9D",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "districts": 1,
                        "blocks": 2,
                        "awcs": 8,
                        "states": 1,
                        "supervisors": 4,
                        'original_name': ["st1"],
                        "fillKey": "Launched"
                    },
                    "st2": {
                        "districts": 2,
                        "blocks": 2,
                        "awcs": 11,
                        "states": 1,
                        "supervisors": 4,
                        'original_name': ["st2"],
                        "fillKey": "Launched"
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
                        'Total AWCs that have launched ICDS CAS <br />'
                        'Number of AWCs launched: 8 <br />'
                        'Number of Blocks launched: 2'
                    )
                },
                "fills": {
                    "Launched": "#fee0d2",
                    "Not launched": "#9D9D9D",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    'block_map': {
                        'states': 1,
                        'blocks': 2,
                        'awcs': 8,
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
                    {
                        "loc_name": "st2",
                        "value": 11
                    },
                    {
                        "loc_name": "st1",
                        "value": 8
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "value": 11
                    },
                    {
                        "loc_name": "st1",
                        "value": 8
                    }
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
                                "y": 19.0,
                                "x": 1491004800000,
                                "all": 0
                            },
                            {
                                "y": 19.0,
                                "x": 1493596800000,
                                "all": 0
                            }
                        ],
                        "key": "Number of AWCs Launched"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st2",
                        "value": 11
                    },
                    {
                        "loc_name": "st1",
                        "value": 8
                    }
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
                    "Total AWCs that have launched ICDS CAS <br />"
                    "Number of AWCs launched: 3 <br />"
                    "Number of Supervisors launched: 2"
                ),
                "tooltips_data": {
                    "s2": {
                        "districts": 1,
                        "states": 1,
                        "supervisors": 1,
                        "blocks": 1,
                        "awcs": 1
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
                        "color": "#006fdf",
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            [
                                "s1",
                                2
                            ],
                            [
                                "s2",
                                1
                            ]
                        ],
                        "key": ""
                    }
                ],
                "format": "number"
            }
        )
