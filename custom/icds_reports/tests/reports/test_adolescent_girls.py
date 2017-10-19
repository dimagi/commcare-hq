from django.test.utils import override_settings

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
                    'month': (2017, 5, 1)
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Total number of adolescent girls who are enrolled for ICDS services",
                    "average": 117.5,
                    "average_format": "number"
                },
                "fills": {
                    "Adolescent Girls": "#006fdf",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "valid": 110,
                        "fillKey": "Adolescent Girls"
                    },
                    "st2": {
                        "valid": 125,
                        "fillKey": "Adolescent Girls"
                    }
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
                    'month': (2017, 5, 1)
                },
                loc_level='state'
            ),
            {
                "location_type": "State",
                "bottom_five": [
                    {
                        "loc_name": "st2",
                        "value": 155
                    },
                    {
                        "loc_name": "st1",
                        "value": 130
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "value": 155
                    },
                    {
                        "loc_name": "st1",
                        "value": 130
                    }
                ],
                "chart_data": [
                    {
                        "color": "#006fdf",
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
                                "y": 285.0,
                                "x": 1491004800000,
                                "all": 0
                            },
                            {
                                "y": 235.0,
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
                        "value": 155
                    },
                    {
                        "loc_name": "st1",
                        "value": 130
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
                },
                location_id='b1',
                loc_level='supervisor'
            ),
            {
                "info": "Total number of adolescent girls who are enrolled for ICDS services",
                "tooltips_data": {
                    "s2": {
                        "valid": 12
                    },
                    "s1": {
                        "valid": 10
                    },
                    None: {
                        "valid": 11
                    }
                },
                "chart_data": [
                    {
                        "color": "#006fdf",
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            [
                                None,
                                11
                            ],
                            [
                                "s1",
                                10
                            ],
                            [
                                "s2",
                                12
                            ]
                        ],
                        "key": "Number Of Girls"
                    }
                ],
                "format": "number"
            }
        )
