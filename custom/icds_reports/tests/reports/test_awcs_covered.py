from django.test.utils import override_settings

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
            )[0],
            {
                "rightLegend": {
                    "info": "Total AWCs that have launched ICDS CAS <br />Number of AWCs launched: 19"
                },
                "fills": {
                    "Launched": "#fee0d2",
                    "Not launched": "#9D9D9D",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "awcs": 8,
                        "fillKey": "Launched"
                    },
                    "st2": {
                        "awcs": 11,
                        "fillKey": "Launched"
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
                        "color": "#fee0d2",
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
                "info": "Number of AWCs launched",
                "tooltips_data": {
                    "s2": {
                        "districts": 0,
                        "supervisors": 0,
                        "blocks": 0,
                        "awcs": 1
                    },
                    "s1": {
                        "districts": 0,
                        "supervisors": 0,
                        "blocks": 0,
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
