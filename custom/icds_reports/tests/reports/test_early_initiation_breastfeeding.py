from django.test.utils import override_settings

from custom.icds_reports.reports.early_initiation_breastfeeding import get_early_initiation_breastfeeding_map, \
    get_early_initiation_breastfeeding_chart, get_early_initiation_breastfeeding_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestEarlyInitiationBreastFeeding(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_early_initiation_breastfeeding_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of children who were put to the breast within one hour of birth."
                            "<br/><br/>Early initiation of breastfeeding ensure the newborn "
                            "recieves the 'first milk' rich in nutrients"
                            " and encourages exclusive breastfeeding practice",
                    "average": 57.142857142857146
                },
                "fills": {
                    "0%-20%": "#de2d26",
                    "20%-60%": "#fc9272",
                    "60%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "in_month": 4,
                        "birth": 3,
                        "fillKey": "60%-100%"
                    },
                    "st2": {
                        "in_month": 3,
                        "birth": 1,
                        "fillKey": "20%-60%"
                    }
                },
                "slug": "early_initiation",
                "label": "Percent Early Initiation of Breastfeeding"
            }

        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_early_initiation_breastfeeding_chart(
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
                        "percent": 75.0
                    },
                    {
                        "loc_name": "st2",
                        "percent": 33.333333333333336
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 75.0
                    },
                    {
                        "loc_name": "st2",
                        "percent": 33.333333333333336
                    }
                ],
                "chart_data": [
                    {
                        "color": "#006fdf",
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            {
                                "y": 0,
                                "x": 1485907200000,
                                "all": 0,
                                "birth": 0
                            },
                            {
                                "y": 0,
                                "x": 1488326400000,
                                "all": 0,
                                "birth": 0
                            },
                            {
                                "y": 0.25,
                                "x": 1491004800000,
                                "all": 8,
                                "birth": 2
                            },
                            {
                                "y": 0.5714285714285714,
                                "x": 1493596800000,
                                "all": 7,
                                "birth": 4
                            }
                        ],
                        "key": "% Early Initiation of Breastfeeding"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 75.0
                    },
                    {
                        "loc_name": "st2",
                        "percent": 33.333333333333336
                    }
                ]
            }

        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_early_initiation_breastfeeding_data(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'aggregation_level': 4
                },
                loc_level='supervisor'
            ),
            {
                "info": "Percentage of children who were put to the breast within one hour of birth."
                        "<br/><br/>Early initiation of breastfeeding ensure the newborn recieves the 'first milk'"
                        " rich in nutrients and encourages exclusive breastfeeding practice",
                "tooltips_data": {
                    "s2": {
                        "in_month": 0,
                        "birth": 0
                    },
                    "s1": {
                        "in_month": 1,
                        "birth": 0
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
                                0.0
                            ],
                            [
                                "s2",
                                0.0
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
