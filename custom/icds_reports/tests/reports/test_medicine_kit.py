from __future__ import absolute_import

from django.test.utils import override_settings

from custom.icds_reports.reports.medicine_kit import get_medicine_kit_data_map, get_medicine_kit_data_chart, \
    get_medicine_kit_sector_data
from django.test import TestCase
from custom.icds_reports.const import ChartColors, MapColors


@override_settings(SERVER_ENVIRONMENT='icds')
class TestMedicineKit(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_medicine_kit_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": "Percentage of AWCs that reported having a Medicine Kit",
                    "average": 66.66666666666667,
                    'extended_info': [
                        {'indicator': 'Total number of AWCs with a Medicine Kit:', 'value': "20"},
                        {'indicator': '% of AWCs with a Medicine Kit:', 'value': '66.67%'}
                    ]
                },
                "label": "Percentage of AWCs that reported having a Medicine Kit",
                "data": {
                    "st1": {
                        "in_month": 9,
                        "original_name": ["st1"],
                        "all": 17,
                        "fillKey": "25%-75%"
                    },
                    "st2": {
                        "in_month": 11,
                        "original_name": ["st2"],
                        "all": 13,
                        "fillKey": "75%-100%"
                    }
                },
                "slug": "medicine_kit",
                "fills": {
                    "0%-25%": MapColors.RED,
                    "25%-75%": MapColors.ORANGE,
                    "75%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                }
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_medicine_kit_data_map(
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
                    "info": "Percentage of AWCs that reported having a Medicine Kit",
                    "average": 52.94117647058823,
                    'extended_info': [
                        {'indicator': 'Total number of AWCs with a Medicine Kit:', 'value': "9"},
                        {'indicator': '% of AWCs with a Medicine Kit:', 'value': '52.94%'}
                    ]
                },
                "label": "Percentage of AWCs that reported having a Medicine Kit",
                "data": {
                    "block_map": {
                        "in_month": 9,
                        "original_name": [
                            "b1",
                            "b2"
                        ],
                        "all": 17,
                        "fillKey": "25%-75%"
                    }
                },
                "slug": "medicine_kit",
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
            get_medicine_kit_data_chart(
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
                        "percent": 1100.0
                    },
                    {
                        "loc_name": "st1",
                        "percent": 900.0
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "percent": 1100.0
                    },
                    {
                        "loc_name": "st1",
                        "percent": 900.0
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
                                "in_month": 0
                            },
                            {
                                "y": 0.0,
                                "x": 1488326400000,
                                "in_month": 0
                            },
                            {
                                "y": 5.5,
                                "x": 1491004800000,
                                "in_month": 11
                            },
                            {
                                "y": 10.0,
                                "x": 1493596800000,
                                "in_month": 20
                            }
                        ],
                        "key": "Percentage of AWCs that reported having a Medicine Kit"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st2",
                        "percent": 1100.0
                    },
                    {
                        "loc_name": "st1",
                        "percent": 900.0
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_medicine_kit_sector_data(
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
                "info": "Percentage of AWCs that reported having a Medicine Kit",
                "tooltips_data": {
                    "s2": {
                        "in_month": 2,
                        "all": 3
                    },
                    "s1": {
                        "in_month": 3,
                        "all": 5
                    }
                },
                "chart_data": [
                    {
                        "color": MapColors.BLUE,
                        "values": [
                            [
                                "s1",
                                0.6
                            ],
                            [
                                "s2",
                                0.6666666666666666
                            ]
                        ],
                        "strokeWidth": 2,
                        "classed": "dashed",
                        "key": ""
                    }
                ]
            }
        )
