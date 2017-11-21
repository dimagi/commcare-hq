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
                    'aggregation_level': 5
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of AWCs that reported having a Medicine Kit",
                    "average": 100.0,
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
                        "all": 9,
                        "fillKey": "75%-100%"
                    },
                    "st2": {
                        "in_month": 11,
                        "all": 11,
                        "fillKey": "75%-100%"
                    }
                },
                "slug": "medicine_kit",
                "label": "Percentage of AWCs that reported having a Medicine Kit"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_medicine_kit_data_chart(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 5
                },
                loc_level='state'
            ),
            {
                "location_type": "State",
                "bottom_five": [
                    {
                        "loc_name": "st1",
                        "percent": 100.0
                    }, 
                    {
                       "loc_name": "st2",
                       "percent": 100.0
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 100.0
                    },
                    {
                        "loc_name": "st2",
                        "percent": 100.0
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
                                "y": 0.3055555555555556,
                                "x": 1491004800000,
                                "in_month": 11
                            },
                            {
                                "y": 1.0,
                                "x": 1493596800000,
                                "in_month": 20
                            }
                        ],
                        "key": "Percentage of AWCs that reported having a Medicine Kit"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 100.0
                    },
                    {
                        "loc_name": "st2",
                        "percent": 100.0
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
                    'aggregation_level': 5
                },
                location_id='b1',
                loc_level='supervisor'
            ),
            {
                "info": "Percentage of AWCs that reported having a Medicine Kit",
                "tooltips_data": {
                    "s2": {
                        "in_month": 2,
                        "all": 4
                    },
                    "s1": {
                        "in_month": 3,
                        "all": 2
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
                                1.5
                            ],
                            [
                                "s2",
                                0.5
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
