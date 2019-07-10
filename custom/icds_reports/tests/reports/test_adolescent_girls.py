from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.adolescent_girls import get_adolescent_girls_data_map, \
    get_adolescent_girls_data_chart, get_adolescent_girls_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds-new')
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
                    "info": "Of the total number of adolescent girls (aged 11-14 years), the percentage of girls "
                            "enrolled for Anganwadi Services",
                    "average": '100.00',
                    'extended_info': [
                        {
                            'indicator': (
                                'Number of adolescent girls (11 - 14 years) who are enrolled for Anganwadi '
                                'Services:'
                            ),
                            'value': "34"
                        },
                        {
                            'indicator': 'Total number of adolescent girls (11 - 14 years) who are registered:',
                            'value': "34"
                        },
                        {
                            'indicator': (
                                'Percentage of registered adolescent girls (11 - 14 years) '
                                'who are enrolled for Anganwadi Services:'
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
                    'st4': {'all': 0, 'valid': 0, 'original_name': ['st4'], 'fillKey': 'Adolescent Girls'}, 
                    'st5': {'all': 0, 'valid': 0, 'original_name': ['st5'], 'fillKey': 'Adolescent Girls'}, 
                    'st6': {'all': 0, 'valid': 0, 'original_name': ['st6'], 'fillKey': 'Adolescent Girls'}, 
                    'st7': {'all': 0, 'valid': 0, 'original_name': ['st7'], 'fillKey': 'Adolescent Girls'}, 
                    'st1': {'all': 17, 'valid': 17, 'original_name': ['st1'], 'fillKey': 'Adolescent Girls'},
                    'st2': {'all': 17, 'valid': 17, 'original_name': ['st2'], 'fillKey': 'Adolescent Girls'},
                    'st3': {'all': 0, 'valid': 0, 'original_name': ['st3'], 'fillKey': 'Adolescent Girls'}},
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
                    "info": "Of the total number of adolescent girls (aged 11-14 years), the percentage of girls "
                            "enrolled for Anganwadi Services",
                    "average": '100.00',
                    'extended_info': [
                        {
                            'indicator': (
                                'Number of adolescent girls (11 - 14 years) who are enrolled for Anganwadi '
                                'Services:'
                            ),
                            'value': "17"
                        },
                        {
                            'indicator': 'Total number of adolescent girls (11 - 14 years) who are registered:',
                            'value': "17"
                        },
                        {
                            'indicator': (
                                'Percentage of registered adolescent girls (11 - 14 years) '
                                'who are enrolled for Anganwadi Services:'
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
                        'valid': 17,
                        'all': 17,
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
                    {'loc_name': 'st3', 'value': 0.0},
                    {'loc_name': 'st4', 'value': 0.0},
                    {'loc_name': 'st5', 'value': 0.0},
                    {'loc_name': 'st6', 'value': 0.0},
                    {'loc_name': 'st7', 'value': 0.0},
                ],
                "top_five": [
                    {'loc_name': 'st1', 'value': 17.0},
                    {'loc_name': 'st2', 'value': 17.0},
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
                            {'y': 38, 'x': 1491004800000, 'all': 38},
                            {'y': 34, 'x': 1493596800000, 'all': 34}
                        ],
                        "key": "Total number of adolescent girls who are enrolled for Anganwadi Services"
                    }
                ],
                "all_locations": [
                    {'loc_name': 'st1', 'value': 17.0},
                    {'loc_name': 'st2', 'value': 17.0},
                    {'loc_name': 'st3', 'value': 0.0},
                    {'loc_name': 'st4', 'value': 0.0},
                    {'loc_name': 'st5', 'value': 0.0},
                    {'loc_name': 'st6', 'value': 0.0},
                    {'loc_name': 'st7', 'value': 0.0},
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
                "info": "Of the total number of adolescent girls (aged 11-14 years), the percentage of girls "
                        "enrolled for Anganwadi Services",
                "tooltips_data": {
                    "s2": {
                        "all": 5,
                        "valid": 5
                    },
                    "s1": {
                        "valid": 3,
                        "all": 3
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
                                3
                            ],
                            [
                                "s2",
                                5
                            ]
                        ],
                        "key": "Number Of Girls"
                    }
                ],
                "format": "number"
            }
        )
