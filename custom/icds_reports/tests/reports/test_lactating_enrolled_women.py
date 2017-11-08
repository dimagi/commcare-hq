from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors
from custom.icds_reports.reports.enrolled_women import get_enrolled_women_data_chart
from custom.icds_reports.reports.lactating_enrolled_women import get_lactating_enrolled_women_data_map, \
    get_lactating_enrolled_women_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestLactatingEnrolledWomen(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_lactating_enrolled_women_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Lactating Mothers enrolled for ICDS services.",
                    "average": 83.0,
                    "average_format": "number"
                },
                "fills": {
                    "Women": "#006fdf",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "valid": 87,
                        "fillKey": "Women"
                    },
                    "st2": {
                        "valid": 79,
                        "fillKey": "Women"
                    }
                },
                "slug": "lactating_enrolled_women",
                "label": ""
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_enrolled_women_data_chart(
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
                        "value": 54
                    },
                    {
                        "loc_name": "st1",
                        "value": 50
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "value": 54
                    },
                    {
                        "loc_name": "st1",
                        "value": 50
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
                                "y": 104.0,
                                "x": 1491004800000,
                                "all": 0
                            },
                            {
                                "y": 155.0,
                                "x": 1493596800000,
                                "all": 0
                            }
                        ],
                        "key": "Total number of pregnant women who are enrolled for ICDS services"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st2",
                        "value": 54
                    },
                    {
                        "loc_name": "st1",
                        "value": 50
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_lactating_enrolled_women_sector_data(
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
                "info": "Lactating Mothers enrolled for ICDS services.",
                "tooltips_data": {
                    "s2": {
                        "valid": 24
                    },
                    "s1": {
                        "valid": 19
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
                                19
                            ],
                            [
                                "s2",
                                24
                            ]
                        ],
                        "key": ""
                    }
                ],
                "format": "number"
            }
        )
