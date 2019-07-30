from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.registered_household import get_registered_household_data_map, \
    get_registered_household_data_chart, get_registered_household_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds-new')
class TestRegisteredHousehold(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_registered_household_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": "Total number of households registered: 6,964",
                    "average": 994.8571428571429,
                    "average_format": "number"
                },
                "fills": {
                    "Household": MapColors.BLUE,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'st4': {'household': 0, 'original_name': ['st4'], 'fillKey': 'Household'}, 
                    'st5': {'household': 0, 'original_name': ['st5'], 'fillKey': 'Household'}, 
                    'st6': {'household': 0, 'original_name': ['st6'], 'fillKey': 'Household'}, 
                    'st7': {'household': 0, 'original_name': ['st7'], 'fillKey': 'Household'}, 
                    'st1': {'household': 3633, 'original_name': ['st1'], 'fillKey': 'Household'}, 
                    'st2': {'household': 3331, 'original_name': ['st2'], 'fillKey': 'Household'}, 
                    'st3': {'household': 0, 'original_name': ['st3'], 'fillKey': 'Household'}
                },
                "slug": "registered_household",
                "label": ""
            }
        )

    def test_map_name_is_different_data(self):
        self.maxDiff = None
        self.assertDictEqual(
            get_registered_household_data_map(
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
                    "info": "Total number of households registered: 3,633",
                    "average": 1816.5,
                    "average_format": "number"
                },
                "fills": {
                    "Household": MapColors.BLUE,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'block_map': {
                        'household': 3633,
                        'original_name': ['b1', 'b2'],
                        'fillKey': 'Household'
                    }
                },
                "slug": "registered_household",
                "label": ""
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_registered_household_data_chart(
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
                    {'loc_name': 'st1', 'value': 3633.0},
                    {'loc_name': 'st2', 'value': 3331.0},
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
                                "y": 6951.0,
                                "x": 1491004800000,
                                "all": 0
                            },
                            {
                                "y": 6964.0,
                                "x": 1493596800000,
                                "all": 0
                            }
                        ],
                        "key": "Registered Households"
                    }
                ],
                "all_locations": [
                    {'loc_name': 'st1', 'value': 3633.0},
                    {'loc_name': 'st2', 'value': 3331.0},
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
            get_registered_household_sector_data(
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
                "info": "Total number of households registered",
                "tooltips_data": {
                    "s2": {
                        "household": 1195
                    },
                    "s1": {
                        "household": 774
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
                                774
                            ],
                            [
                                "s2",
                                1195
                            ]
                        ],
                        "key": ""
                    }
                ],
                "format": "number"
            }
        )
