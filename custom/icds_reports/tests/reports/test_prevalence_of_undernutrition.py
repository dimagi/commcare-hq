from __future__ import absolute_import
from collections import OrderedDict

from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors
from custom.icds_reports.reports.prevalence_of_undernutrition import get_prevalence_of_undernutrition_data_map, \
    get_prevalence_of_undernutrition_data_chart, get_prevalence_of_undernutrition_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestPrevalenceOfUndernutrition(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_prevalence_of_undernutrition_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1)
                },
                loc_level='state'
            )[0],
            {
                'rightLegend': {
                    'info': u'Percentage of children between 0-5 years enrolled for ICDS services'
                            u' with weight-for-age less than -2 standard deviations'
                            u' of the WHO Child Growth Standards median.'
                            u' <br/><br/>Children who are moderately or severely underweight'
                            u' have a higher risk of mortality',
                    'average': 17.593528816986854
                },
                'fills': OrderedDict(
                    [
                        ('0%-20%', '#fee0d2'),
                        ('20%-35%', '#fc9272'),
                        ('35%-100%', '#de2d26'),
                        ('defaultFill', '#9D9D9D')
                    ]
                ),
                'data': {
                    u'st1': {
                        'total': 2375,
                        'severely_underweight': 40,
                        'moderately_underweight': 450,
                        'fillKey': '20%-35%',
                        'normal': 1820
                    },
                    u'st2': {
                        'total': 2570,
                        'severely_underweight': 70,
                        'moderately_underweight': 420,
                        'fillKey': '0%-20%', 'normal': 1975
                    }
                },
                'slug': 'moderately_underweight',
                'label': 'Percent of Children Underweight (0-5 years)'
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_prevalence_of_undernutrition_data_chart(
                'icds-cas',
                config={
                    'month': (2017, 5, 1)
                },
                loc_level='state'
            ),
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
                                "y": 0.4976228209191759,
                                "x": 1491004800000,
                                "all": 6310
                            },
                            {
                                "y": 0.5897435897435898,
                                "x": 1493596800000,
                                "all": 6435
                            }
                        ],
                        "key": "% Normal"
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
                                "y": 0.1434231378763867,
                                "x": 1491004800000,
                                "all": 6310
                            },
                            {
                                "y": 0.1351981351981352,
                                "x": 1493596800000,
                                "all": 6435
                            }
                        ],
                        "key": "% Moderately Underweight (-2 SD)"
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
                                "y": 0.011885895404120444,
                                "x": 1491004800000,
                                "all": 6310
                            },
                            {
                                "y": 0.017094017094017096,
                                "x": 1493596800000,
                                "all": 6435
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
            get_prevalence_of_undernutrition_sector_data(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                },
                location_id='b1',
                loc_level='supervisor'
            ),
            {
                "info": "Percentage of children between 0-5 years enrolled for ICDS services with weight-for-age"
                        " less than -2 standard deviations of the WHO Child Growth Standards median."
                        " <br/><br/>Children who are moderately "
                        "or severely underweight have a higher risk of mortality",
                "tooltips_data": {
                    u"s2": {
                        "total": 326,
                        "severely_underweight": 4,
                        "moderately_underweight": 74,
                        "normal": 236
                    },
                    u"s1": {
                        "total": 144,
                        "severely_underweight": 8,
                        "moderately_underweight": 42,
                        "normal": 92
                    },
                    None: {
                        "total": 235,
                        "severely_underweight": 6,
                        "moderately_underweight": 58,
                        "normal": 164
                    }
                },
                "chart_data": [
                    {
                        "color": "#006fdf",
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            [
                                None,
                                0.2723404255319149
                            ],
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
