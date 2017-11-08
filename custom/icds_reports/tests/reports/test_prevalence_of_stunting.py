from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors
from custom.icds_reports.reports.prevalence_of_stunting import get_prevalence_of_stunting_data_map, \
    get_prevalence_of_stunting_data_chart
from custom.icds_reports.reports.prevalence_of_undernutrition import get_prevalence_of_undernutrition_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestPrevalenceOfStunting(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_prevalence_of_stunting_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of children (6-60 months) enrolled for ICDS services with "
                            "height-for-age below -2Z standard deviations of "
                            "the WHO Child Growth Standards median.<br/><br/>Stunting "
                            "is a sign of chronic undernutrition and has long "
                            "lasting harmful consequences on the growth of a child",
                    "average": "2.77"
                },
                "fills": {
                    "0%-25%": "#fee0d2",
                    "25%-38%": "#fc9272",
                    "38%-100%": "#de2d26",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "severe": 3,
                        "moderate": 5,
                        "normal": 2,
                        "total_measured": 7,
                        "total": 449,
                        "fillKey": "0%-25%"
                    },
                    "st2": {
                        "severe": 13,
                        "moderate": 5,
                        "normal": 13,
                        "total_measured": 25,
                        "total": 490,
                        "fillKey": "0%-25%"
                    }
                },
                "slug": "severe",
                "label": "Percent of Children Stunted (6 - 60 months)"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_prevalence_of_stunting_data_chart(
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
                        "percent": 1.78173719376392
                    },
                    {
                        "loc_name": "st2",
                        "percent": 3.673469387755102
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 1.78173719376392
                    },
                    {
                        "loc_name": "st2",
                        "percent": 3.673469387755102
                    }
                ],
                "chart_data": [
                    {
                        "color": ChartColors.PINK,
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
                                "y": 0.0031120331950207467,
                                "x": 1491004800000,
                                "all": 964
                            },
                            {
                                "y": 0.01597444089456869,
                                "x": 1493596800000,
                                "all": 939
                            }
                        ],
                        "key": "% normal"
                    },
                    {
                        "color": ChartColors.ORANGE,
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
                                "y": 0.004149377593360996,
                                "x": 1491004800000,
                                "all": 964
                            },
                            {
                                "y": 0.010649627263045794,
                                "x": 1493596800000,
                                "all": 939
                            }
                        ],
                        "key": "% moderately stunted"
                    },
                    {
                        "color": ChartColors.RED,
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
                                "y": 0.008298755186721992,
                                "x": 1491004800000,
                                "all": 964
                            },
                            {
                                "y": 0.01703940362087327,
                                "x": 1493596800000,
                                "all": 939
                            }
                        ],
                        "key": "% severely stunted"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 1.78173719376392
                    },
                    {
                        "loc_name": "st2",
                        "percent": 3.673469387755102
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_prevalence_of_undernutrition_sector_data(
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
                "info": "Percentage of children between 0-5 years enrolled for ICDS services"
                        " with weight-for-age less than -2 standard deviations"
                        " of the WHO Child Growth Standards median. <br/><br/>"
                        "Children who are moderately or severely underweight have a higher risk of mortality",
                "tooltips_data": {
                    "s2": {
                        "total": 163,
                        "severely_underweight": 2,
                        "moderately_underweight": 37,
                        "normal": 118
                    },
                    "s1": {
                        "total": 72,
                        "severely_underweight": 4,
                        "moderately_underweight": 21,
                        "normal": 46
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
                                0.3472222222222222
                            ],
                            [
                                "s2",
                                0.2392638036809816
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
