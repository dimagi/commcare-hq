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
        print get_prevalence_of_undernutrition_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1)
                },
                loc_level='state'
            )[0]
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
                    'average': 17.593528816986854,
                    'extended_info': [
                        {'indicator': 'Total Children weighed in given month:', 'value': 4945},
                        {'indicator': '% Unweighed:', 'value': '5.66%'},
                        {'indicator': '% Severely Underweight:', 'value': '0.00%'},
                        {'indicator': '% Moderately Underweight:', 'value': '17.59%'},
                        {'indicator': '% Normal:', 'value': '76.74%'}]
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
                    'st1': {
                        'total': 2375,
                        'severely_underweight': 40,
                        'moderately_underweight': 450,
                        'fillKey': '20%-35%',
                        'original_name': [],
                        'normal': 1820
                    },
                    'st2': {
                        'total': 2570,
                        'severely_underweight': 70,
                        'moderately_underweight': 420,
                        'original_name': [],
                        'fillKey': '0%-20%',
                        'normal': 1975
                    }
                },
                'slug': 'moderately_underweight',
                'label': 'Percent of Children Underweight (0-5 years)'
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_prevalence_of_undernutrition_data_map(
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
                'rightLegend': {
                    'info': u'Percentage of children between 0-5 years enrolled for ICDS services'
                            u' with weight-for-age less than -2 standard deviations'
                            u' of the WHO Child Growth Standards median.'
                            u' <br/><br/>Children who are moderately or severely underweight'
                            u' have a higher risk of mortality',
                    'average': 18.94736842105263,
                    'extended_info': [
                        {'indicator': 'Total Children weighed in given month:', 'value': 475},
                        {'indicator': '% Unweighed:', 'value': '4.42%'},
                        {'indicator': '% Severely Underweight:', 'value': '0.00%'},
                        {'indicator': '% Moderately Underweight:', 'value': '18.95%'},
                        {'indicator': '% Normal:', 'value': '76.63%'}
                    ]
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
                    'block_map': {
                        'severely_underweight': 8,
                        'moderately_underweight': 90,
                        'normal': 364,
                        'total': 475,
                        'original_name': ['b1', 'b2'],
                        'fillKey': '20%-35%'
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
                        "percent": 19.06614785992218
                    },
                    {
                        "loc_name": "st1",
                        "percent": 20.63157894736842
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "percent": 19.06614785992218
                    },
                    {
                        "loc_name": "st1",
                        "percent": 20.63157894736842
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
                                "y": 0.6144814090019569,
                                "x": 1491004800000,
                                "all": 5110
                            },
                            {
                                "y": 0.7674418604651163,
                                "x": 1493596800000,
                                "all": 4945
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
                                "y": 0.1771037181996086,
                                "x": 1491004800000,
                                "all": 5110
                            },
                            {
                                "y": 0.17593528816986856,
                                "x": 1493596800000,
                                "all": 4945
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
                                "y": 0.014677103718199608,
                                "x": 1491004800000,
                                "all": 5110
                            },
                            {
                                "y": 0.022244691607684528,
                                "x": 1493596800000,
                                "all": 4945
                            }
                        ],
                        "key": "% Severely Underweight (-3 SD) "
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st2",
                        "percent": 19.06614785992218
                    },
                    {
                        "loc_name": "st1",
                        "percent": 20.63157894736842
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
