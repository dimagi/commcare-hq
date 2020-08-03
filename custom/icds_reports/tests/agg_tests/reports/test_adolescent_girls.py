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
                    "info": "Of the total number of adolescent girls (aged 11-14 years), "
                            "the percentage of adolescent girls who are out of school",
                    "average": '8.33',
                    'extended_info': [
                        {
                            'indicator': (
                                'Number of adolescent girls (11-14 years) who are out of school:'
                            ),
                            'value': "2"
                        },
                        {
                            'indicator': 'Total Number of adolescent girls (11-14 years) who are registered:',
                            'value': "24"
                        },
                        {
                            'indicator': (
                                'Percentage of adolescent girls (11-14 years) who are out of school:'
                            ),
                            'value': '8.33%'
                        }
                    ]
                },
                "fills": {
                    "Out of school Adolescent Girls": MapColors.BLUE,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'st4': {'all': 0, 'valid': 0, 'original_name': ['st4'],
                            'fillKey': 'Out of school Adolescent Girls'},
                    'st5': {'all': 0, 'valid': 0, 'original_name': ['st5'],
                            'fillKey': 'Out of school Adolescent Girls'},
                    'st6': {'all': 0, 'valid': 0, 'original_name': ['st6'],
                            'fillKey': 'Out of school Adolescent Girls'},
                    'st7': {'all': 3, 'valid': 2, 'original_name': ['st7'],
                            'fillKey': 'Out of school Adolescent Girls'},
                    'st1': {'all': 10, 'valid': 0, 'original_name': ['st1'],
                            'fillKey': 'Out of school Adolescent Girls'},
                    'st2': {'all': 11, 'valid': 0, 'original_name': ['st2'],
                            'fillKey': 'Out of school Adolescent Girls'},
                    'st3': {'all': 0, 'valid': 0, 'original_name': ['st3'],
                            'fillKey': 'Out of school Adolescent Girls'}},
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
                    "info": "Of the total number of adolescent girls (aged 11-14 years), "
                            "the percentage of adolescent girls who are out of school",
                    "average": '0.00',
                    'extended_info': [
                        {
                            'indicator': 'Number of adolescent girls (11-14 years) who are out of school:',
                            'value': "0"
                        },
                        {
                            'indicator': 'Total Number of adolescent girls (11-14 years) who are registered:',
                            'value': "10"
                        },
                        {
                            'indicator': (
                                'Percentage of adolescent girls (11-14 years) who are out of school:'
                            ),
                            'value': '0.00%'
                        }
                    ]
                },
                "fills": {
                    "Out of school Adolescent Girls": MapColors.BLUE,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'block_map': {
                        'valid': 0,
                        'all': 10,
                        'original_name': ['b1', 'b2'],
                        'fillKey': 'Out of school Adolescent Girls'}
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
                    {'loc_name': 'st3', 'value': 0.0},
                    {'loc_name': 'st4', 'value': 0.0},
                    {'loc_name': 'st5', 'value': 0.0},
                    {'loc_name': 'st6', 'value': 0.0},
                    {'loc_name': 'st7', 'value': 2.0},
                ],
                "top_five": [
                    {'loc_name': 'st1', 'value': 0.0},
                    {'loc_name': 'st2', 'value': 0.0},
                    {'loc_name': 'st3', 'value': 0.0},
                    {'loc_name': 'st4', 'value': 0.0},
                    {'loc_name': 'st5', 'value': 0.0},
                ],
                "chart_data": [
                    {
                        "color": ChartColors.BLUE,
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            {'y': 0, 'x': 1485907200000, 'all': 0},
                            {'y': 0, 'x': 1488326400000, 'all': 0},
                            {'y': 2, 'x': 1491004800000, 'all': 33},
                            {'y': 2, 'x': 1493596800000, 'all': 24}
                        ],
                        "key": "Number of adolescent girls (11-14 years) who are out of school"
                    }
                ],
                "all_locations": [
                    {'loc_name': 'st1', 'value': 0.0},
                    {'loc_name': 'st2', 'value': 0.0},
                    {'loc_name': 'st3', 'value': 0.0},
                    {'loc_name': 'st4', 'value': 0.0},
                    {'loc_name': 'st5', 'value': 0.0},
                    {'loc_name': 'st6', 'value': 0.0},
                    {'loc_name': 'st7', 'value': 2.0},

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
                "info":  "Of the total number of adolescent girls (aged 11-14 years), "
                         "the percentage of adolescent girls who are out of school",
                "tooltips_data": {
                    "s2": {
                        "all": 4,
                        "valid": 0
                    },
                    "s1": {
                        "valid": 0,
                        "all": 1
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
                                0
                            ],
                            [
                                "s2",
                                0
                            ]
                        ],
                        "key": "Number Of Girls"
                    }
                ],
                "format": "number"
            }
        )
