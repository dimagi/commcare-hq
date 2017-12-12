from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors
from custom.icds_reports.reports.registered_household import get_registered_household_data_map, \
    get_registered_household_data_chart, get_registered_household_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
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
            )[0],
            {
                "rightLegend": {
                    "info": "Total number of households registered: 6964",
                    "average": 3482.0,
                    "average_format": "number"
                },
                "fills": {
                    "Household": "#006fdf",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "household": 3633,
                        'original_name': [],
                        "fillKey": "Household"
                    },
                    "st2": {
                        "household": 3331,
                        'original_name': [],
                        "fillKey": "Household"
                    }
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
            )[0],
            {
                "rightLegend": {
                    "info": "Total number of households registered: 3633",
                    "average": 1816.5,
                    "average_format": "number"
                },
                "fills": {
                    "Household": "#006fdf",
                    "defaultFill": "#9D9D9D"
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
                    {
                        "loc_name": "st1",
                        "value": 3633
                    },
                    {
                        "loc_name": "st2",
                        "value": 3331
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "value": 3633
                    },
                    {
                        "loc_name": "st2",
                        "value": 3331
                    }
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
                                "y": 6964.0,
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
                    {
                        "loc_name": "st1",
                        "value": 3633
                    },
                    {
                        "loc_name": "st2",
                        "value": 3331
                    }
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
                        "color": "#006fdf",
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
