from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors
from custom.icds_reports.reports.medicine_kit import get_medicine_kit_data_map, get_medicine_kit_data_chart, \
    get_medicine_kit_sector_data
from django.test import TestCase


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
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of AWCs with a Medicine Kit",
                    "average": 40.0,
                    'extended_info': [
                        {'indicator': 'Total number of AWCs with a Medicine Kit:', 'value': 20},
                        {'indicator': '% of AWCs with a Medicine Kit:', 'value': '40.00%'}
                    ]
                },
                "fills": {
                    "0%-25%": "#de2d26",
                    "25%-75%": "#fc9272",
                    "75%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "in_month": 9,
                        "all": 26,
                        'original_name': [],
                        "fillKey": "25%-75%"
                    },
                    "st2": {
                        "in_month": 11,
                        "all": 24,
                        'original_name': [],
                        "fillKey": "25%-75%"
                    }
                },
                "slug": "medicine_kit",
                "label": "Percent AWCs with Medicine Kit"
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
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of AWCs with a Medicine Kit",
                    "average": 34.61538461538461,
                    'extended_info': [
                        {'indicator': 'Total number of AWCs with a Medicine Kit:', 'value': 9},
                        {'indicator': '% of AWCs with a Medicine Kit:', 'value': '34.62%'}
                    ]
                },
                "fills": {
                    "0%-25%": "#de2d26",
                    "25%-75%": "#fc9272",
                    "75%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    'block_map': {
                        'in_month': 9,
                        'original_name': ['b1', 'b2'],
                        'all': 26,
                        'fillKey': '25%-75%'
                    }
                },
                "slug": "medicine_kit",
                "label": "Percent AWCs with Medicine Kit"
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
                        "percent": 45.833333333333336
                    },
                    {
                        "loc_name": "st1",
                        "percent": 34.61538461538461
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "percent": 45.833333333333336
                    },
                    {
                        "loc_name": "st1",
                        "percent": 34.61538461538461
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
                                "y": 0.22,
                                "x": 1491004800000,
                                "in_month": 11
                            },
                            {
                                "y": 0.4,
                                "x": 1493596800000,
                                "in_month": 20
                            }
                        ],
                        "key": "% of AWCs with a Medicine Kit."
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st2",
                        "percent": 45.833333333333336
                    },
                    {
                        "loc_name": "st1",
                        "percent": 34.61538461538461
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
                "info": "Percentage of AWCs with a Medicine Kit",
                "tooltips_data": {
                    "s2": {
                        "in_month": 2,
                        "all": 7
                    },
                    "s1": {
                        "in_month": 3,
                        "all": 7
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
                                0.42857142857142855
                            ],
                            [
                                "s2",
                                0.2857142857142857
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
