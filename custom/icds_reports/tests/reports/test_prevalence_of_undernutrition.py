from datetime import datetime

from django.test.utils import override_settings

from django.test import TestCase

from custom.icds_reports.reports.prevalence_of_undernutrition_data.prevalence_of_undernutrition_factory import \
    get_prevalence_of_undernutrition_report_data_instance


@override_settings(SERVER_ENVIRONMENT='icds')
class TestPrevalenceOfUndernutrition(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_prevalence_of_undernutrition_report_data_instance(
                mode='map',
                domain='icds-cas',
                location_id=None,
                date=datetime(2017, 5, 1)
            ).get_data()[0],
            {
                'rightLegend': {
                    'info': u'Percentage of children between 0-5 years enrolled for ICDS services'
                            u' with weight-for-age less than -2 standard deviations'
                            u' of the WHO Child Growth Standards median.'
                            u' <br/><br/>Children who are moderately or severely underweight'
                            u' have a higher risk of mortality',
                    'average': 17
                },
                "fills": {
                    "0%-20%": "#fee0d2",
                    "20%-35%": "#fc9272",
                    "35%-100%": "#de2d26",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "total": 475,
                        "severely_underweight": 8,
                        "moderately_underweight": 90,
                        "fillKey": "20%-35%",
                        "normal": 364
                    },
                    "st2": {
                        "total": 514,
                        "severely_underweight": 14,
                        "moderately_underweight": 84,
                        "fillKey": "0%-20%",
                        "normal": 395
                    }
                },
                "slug": "moderately_underweight",
                "label": "Percent of Children Underweight (0-5 years)"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_prevalence_of_undernutrition_report_data_instance(
                mode='chart',
                domain='icds-cas',
                location_id=None,
                date=datetime(2017, 5, 1)
            ).get_data(),
            {
                "location_type": "State",
                "bottom_five": [
                    {
                        "loc_name": "st2",
                        "percent": 14.648729446935725
                    },
                    {
                        "loc_name": "st1",
                        "percent": 15.857605177993527
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "percent": 14.648729446935725
                    },
                    {
                        "loc_name": "st1",
                        "percent": 15.857605177993527
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
                                "y": 0.4976228209191759,
                                "x": 1491004800000,
                                "all": 1262
                            },
                            {
                                "y": 0.5897435897435898,
                                "x": 1493596800000,
                                "all": 1287
                            }
                        ],
                        "key": "% Normal"
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
                                "y": 0.1434231378763867,
                                "x": 1491004800000,
                                "all": 1262
                            },
                            {
                                "y": 0.1351981351981352,
                                "x": 1493596800000,
                                "all": 1287
                            }
                        ],
                        "key": "% Moderately Underweight (-2 SD)"
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
                                "y": 0.011885895404120444,
                                "x": 1491004800000,
                                "all": 1262
                            },
                            {
                                "y": 0.017094017094017096,
                                "x": 1493596800000,
                                "all": 1287
                            }
                        ],
                        "key": "% Severely Underweight (-3 SD) "
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st2",
                        "percent": 14.648729446935725
                    },
                    {
                        "loc_name": "st1",
                        "percent": 15.857605177993527
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_prevalence_of_undernutrition_report_data_instance(
                mode='map',
                domain='icds-cas',
                location_id='b1',
                date=datetime(2017, 5, 1)
            ).get_data(),
            {
                "info": "Percentage of children between 0-5 years enrolled for ICDS services with weight-for-age"
                        " less than -2 standard deviations of the WHO Child Growth Standards median."
                        " <br/><br/>Children who are moderately "
                        "or severely underweight have a higher risk of mortality",
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
