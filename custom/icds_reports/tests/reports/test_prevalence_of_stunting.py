from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.prevalence_of_stunting import get_prevalence_of_stunting_data_map, \
    get_prevalence_of_stunting_data_chart, get_prevalence_of_stunting_sector_data
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
            ),
            {
                "rightLegend": {
                    "info": "Percentage of children (6 - 60 months) enrolled for ICDS services with "
                            "height-for-age below -2Z standard deviations of "
                            "the WHO Child Growth Standards median.<br/><br/>Stunting "
                            "is a sign of chronic undernutrition and has long "
                            "lasting harmful consequences on the growth of a child",
                    "average": "1.99",
                    'extended_info': [
                        {'indicator': 'Total Children (6 - 60 months) weighed in given month:', 'value': '939'},
                        {'indicator': 'Total Children (6 - 60 months) with height measured in given month:',
                         'value': '32'},
                        {'indicator': '% Unmeasured (6 - 60 months):', 'value': '96.38%'},
                        {'indicator': '% Severely stunted (6 - 60 months):', 'value': '1.17%'},
                        {'indicator': '% Moderately stunted (6 - 60 months):', 'value': '0.85%'},
                        {'indicator': '% Normal (6 - 60 months):', 'value': '1.60%'}
                    ]
                },
                "fills": {
                    "0%-25%": MapColors.PINK,
                    "25%-38%": MapColors.ORANGE,
                    "38%-100%": MapColors.RED,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    "st1": {
                        "severe": 2,
                        "moderate": 3,
                        "normal": 2,
                        "total_measured": 7,
                        "total": 449,
                        'original_name': ["st1"],
                        "fillKey": "0%-25%"
                    },
                    "st2": {
                        "severe": 9,
                        "moderate": 5,
                        "normal": 13,
                        "total_measured": 25,
                        "total": 490,
                        'original_name': ["st2"],
                        "fillKey": "0%-25%"
                    }
                },
                "slug": "severe",
                "label": "Percent of Children Stunted (6 - 60 months)"
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_prevalence_of_stunting_data_map(
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
                    "info": "Percentage of children (6 - 60 months) enrolled for ICDS services with "
                            "height-for-age below -2Z standard deviations of "
                            "the WHO Child Growth Standards median.<br/><br/>Stunting "
                            "is a sign of chronic undernutrition and has long "
                            "lasting harmful consequences on the growth of a child",
                    "average": "1.11",
                    'extended_info': [
                        {'indicator': 'Total Children (6 - 60 months) weighed in given month:', 'value': '449'},
                        {'indicator': 'Total Children (6 - 60 months) with height measured in given month:',
                         'value': '7'},
                        {'indicator': '% Unmeasured (6 - 60 months):', 'value': '98.44%'},
                        {'indicator': '% Severely stunted (6 - 60 months):', 'value': '0.45%'},
                        {'indicator': '% Moderately stunted (6 - 60 months):', 'value': '0.67%'},
                        {'indicator': '% Normal (6 - 60 months):', 'value': '0.45%'}
                    ]
                },
                "fills": {
                    "0%-25%": MapColors.PINK,
                    "25%-38%": MapColors.ORANGE,
                    "38%-100%": MapColors.RED,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'block_map': {
                        'moderate': 3,
                        'total_measured': 7,
                        'normal': 2,
                        'original_name': ['b1', 'b2'],
                        'severe': 2,
                        'total': 449,
                        'fillKey': '0%-25%'
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
                        "percent": 1.1135857461024499
                    },
                    {
                        "loc_name": "st2",
                        "percent": 2.857142857142857
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 1.1135857461024499
                    },
                    {
                        "loc_name": "st2",
                        "percent": 2.857142857142857
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
                                "y": 0.008519701810436636,
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
                                "y": 0.005186721991701245,
                                "x": 1491004800000,
                                "all": 964
                            },
                            {
                                "y": 0.011714589989350373,
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
                        "percent": 1.1135857461024499
                    },
                    {
                        "loc_name": "st2",
                        "percent": 2.857142857142857
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_prevalence_of_stunting_sector_data(
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
                "info": "Percentage of children (6-60 months) enrolled for ICDS services with height-for-age below"
                        " -2Z standard deviations of the WHO Child Growth Standards median."
                        "<br/><br/>Stunting is a sign of chronic undernutrition "
                        "and has long lasting harmful consequences on the growth of a child",
                "tooltips_data": {
                    "s2": {
                        "total": 150,
                        "severe": 0,
                        "moderate": 2,
                        "total_measured": 4,
                        "normal": 2
                    },
                    "s1": {
                        "total": 70,
                        "severe": 0,
                        "moderate": 0,
                        "total_measured": 0,
                        "normal": 0
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
                                0.0
                            ],
                            [
                                "s2",
                                0.013333333333333334
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
