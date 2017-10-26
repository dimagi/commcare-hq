from django.test.utils import override_settings

from custom.icds_reports.reports.prevalence_of_severe import get_prevalence_of_severe_data_map, \
    get_prevalence_of_severe_data_chart, get_prevalence_of_severe_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestPrevalenceOfSevere(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_prevalence_of_severe_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of children between 6 - 60 months enrolled for ICDS services with weight-for-height below -2 standard deviations of the WHO Child Growth Standards median. <br/><br/>Wasting in children is a symptom of acute undernutrition usually as a consequence of insufficient food intake or a high incidence of infectious diseases. Severe Acute Malnutrition (SAM) is nutritional status for a child who has severe wasting (weight-for-height) below -3 Z and Moderate Acute Malnutrition (MAM) is nutritional status for a child that has moderate wasting (weight-for-height) below -2Z.",
                    "average": "1.05"
                },
                "fills": {
                    "0%-5%": "#fee0d2",
                    "5%-7%": "#fc9272",
                    "7%-100%": "#de2d26",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "severe": 0,
                        "moderate": 4,
                        "normal": 5,
                        "total_measured": 7,
                        "total": 454,
                        "fillKey": "0%-5%"
                    },
                    "st2": {
                        "severe": 2,
                        "moderate": 4,
                        "normal": 16,
                        "total_measured": 25,
                        "total": 497,
                        "fillKey": "0%-5%"
                    }
                },
                "slug": "severe",
                "label": "Percent of Children Wasted (6 - 60 months)"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_prevalence_of_severe_data_chart(
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
                        "percent": 0.8810572687224669
                    },
                    {
                        "loc_name": "st2",
                        "percent": 1.2072434607645874
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 0.8810572687224669
                    },
                    {
                        "loc_name": "st2",
                        "percent": 1.2072434607645874
                    }
                ],
                "chart_data": [
                    {
                        "color": "#fee0d2",
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
                                "y": 0.0061162079510703364,
                                "x": 1491004800000,
                                "all": 981
                            },
                            {
                                "y": 0.022082018927444796,
                                "x": 1493596800000,
                                "all": 951
                            }
                        ],
                        "key": "% normal"
                    },
                    {
                        "color": "#fc9272",
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
                                "y": 0.0010193679918450561,
                                "x": 1491004800000,
                                "all": 981
                            },
                            {
                                "y": 0.008412197686645636,
                                "x": 1493596800000,
                                "all": 951
                            }
                        ],
                        "key": "% moderately wasted (moderate acute malnutrition)"
                    },
                    {
                        "color": "#de2d26",
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
                                "y": 0.0020387359836901123,
                                "x": 1491004800000,
                                "all": 981
                            },
                            {
                                "y": 0.002103049421661409,
                                "x": 1493596800000,
                                "all": 951
                            }
                        ],
                        "key": "% severely wasted (severe acute malnutrition)"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 0.8810572687224669
                    },
                    {
                        "loc_name": "st2",
                        "percent": 1.2072434607645874
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_prevalence_of_severe_sector_data(
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
                "info": "Percentage of children between 6 - 60 months enrolled for ICDS services with "
                        "weight-for-height below -3 standard deviations of the WHO Child Growth Standards"
                        " median.<br/><br/>Severe Acute Malnutrition (SAM) or wasting in"
                        " children is a symptom of acute undernutrition usually as "
                        "a consequence of insufficient food intake or a high incidence of infectious diseases.",
                "tooltips_data": {
                    "s2": {
                        "total": 153,
                        "severe": 0,
                        "moderate": 3,
                        "total_measured": 4,
                        "normal": 1
                    },
                    "s1": {
                        "total": 71,
                        "severe": 0,
                        "moderate": 0,
                        "total_measured": 0,
                        "normal": 0
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
                                0.0196078431372549
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
