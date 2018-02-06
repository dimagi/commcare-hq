from __future__ import absolute_import

from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.prevalence_of_undernutrition import get_prevalence_of_undernutrition_data_map, \
    get_prevalence_of_undernutrition_data_chart, get_prevalence_of_undernutrition_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestPrevalenceOfUndernutrition(TestCase):
    maxDiff = None

    def test_map_data_keys(self):
        data = get_prevalence_of_undernutrition_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
            },
            loc_level='state'
        )
        self.assertEquals(len(data), 5)
        self.assertIn('rightLegend', data)
        self.assertIn('fills', data)
        self.assertIn('data', data)
        self.assertIn('slug', data)
        self.assertIn('label', data)

    def test_map_data_right_legend_keys(self):
        data = get_prevalence_of_undernutrition_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
            },
            loc_level='state'
        )['rightLegend']
        self.assertEquals(len(data), 3)
        self.assertIn('info', data)
        self.assertIn('average', data)
        self.assertIn('extended_info', data)

    def test_map_data(self):
        data = get_prevalence_of_undernutrition_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
            },
            loc_level='state'
        )
        self.assertDictEqual(
            data['data'],
            {
                'st1': {
                    'total': 1585,
                    'severely_underweight': 40,
                    'moderately_underweight': 320,
                    'fillKey': '20%-35%',
                    'original_name': ["st1"],
                    'normal': 1225,
                    'eligible': 2375
                },
                'st2': {
                    'total': 1895,
                    'severely_underweight': 60,
                    'moderately_underweight': 330,
                    'original_name': ["st2"],
                    'fillKey': '20%-35%',
                    'normal': 1505,
                    'eligible': 2570
                }
            }
        )

    def test_map_data_right_legend_info(self):
        data = get_prevalence_of_undernutrition_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
            },
            loc_level='state'
        )
        expected = (
            u'Percentage of children between 0 - 5 years enrolled for Anganwadi Services'
            u' with weight-for-age less than -2 standard deviations'
            u' of the WHO Child Growth Standards median.'
            u' <br/><br/>Children who are moderately or severely underweight'
            u' have a higher risk of mortality'
        )
        self.assertEquals(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_prevalence_of_undernutrition_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
            },
            loc_level='state'
        )
        self.assertEquals(data['rightLegend']['average'], 21.64670434399008)

    def test_map_data_right_legend_extended_info(self):
        data = get_prevalence_of_undernutrition_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
            },
            loc_level='state'
        )
        self.assertListEqual(
            data['rightLegend']['extended_info'],
            [
                {'indicator': 'Total Children (0 - 5 years) weighed in given month:', 'value': '3,480'},
                {'indicator': 'Number of children unweighed (0 - 5 years):', 'value': '1,465'},
                {'indicator': '% Severely Underweight (0 - 5 years):', 'value': '2.87%'},
                {'indicator': '% Moderately Underweight (0 - 5 years):', 'value': '18.68%'},
                {'indicator': '% Normal (0 - 5 years):', 'value': '78.45%'}
            ]
        )

    def test_map_data_fills(self):
        data = get_prevalence_of_undernutrition_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
            },
            loc_level='state'
        )
        self.assertDictEqual(
            data['fills'],
            {
                "0%-20%": MapColors.PINK,
                "20%-35%": MapColors.ORANGE,
                "35%-100%": MapColors.RED,
                "defaultFill": MapColors.GREY
            }
        )

    def test_map_data_slug(self):
        data = get_prevalence_of_undernutrition_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
            },
            loc_level='state'
        )
        self.assertEquals(data['slug'], 'moderately_underweight')

    def test_map_data_label(self):
        data = get_prevalence_of_undernutrition_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
            },
            loc_level='state'
        )
        self.assertEquals(data['label'], 'Percent of Children Underweight (0 - 5 years)')

    def test_map_name_two_locations_represent_by_one_topojson(self):
        data = get_prevalence_of_undernutrition_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
        )
        self.assertDictEqual(
            data['data'],
            {
                'block_map': {
                    'severely_underweight': 8,
                    'moderately_underweight': 64,
                    'normal': 245,
                    'total': 317,
                    'eligible': 475,
                    'original_name': ['b1', 'b2'],
                    'fillKey': '20%-35%'
                }
            }
        )

    def test_average_with_two_locations_represent_by_one_topojson(self):
        data = get_prevalence_of_undernutrition_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
        )
        self.assertEquals(data['rightLegend']['average'], 22.743014091234773)

    def test_chart_data_keys_length(self):
        data = get_prevalence_of_undernutrition_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1)
            },
            loc_level='state'
        )
        self.assertEquals(len(data), 5)

    def test_chart_data_location_type(self):
        data = get_prevalence_of_undernutrition_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1)
            },
            loc_level='state'
        )
        self.assertEquals(data['location_type'], 'State')

    def test_chart_data_bottom_five(self):
        data = get_prevalence_of_undernutrition_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1)
            },
            loc_level='state'
        )
        self.assertListEqual(
            data['bottom_five'],
            [
                {
                    "loc_name": "st2",
                    "percent": 20.58047493403694
                },
                {
                    "loc_name": "st1",
                    "percent": 22.71293375394322
                },
            ]
        )

    def test_chart_data_top_five(self):
        data = get_prevalence_of_undernutrition_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1)
            },
            loc_level='state'
        )
        self.assertListEqual(
            data['top_five'],
            [
                {
                    "loc_name": "st2",
                    "percent": 20.58047493403694
                },
                {
                    "loc_name": "st1",
                    "percent": 22.71293375394322
                },
            ]
        )

    def test_chart_data_elements_length(self):
        data = get_prevalence_of_undernutrition_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1)
            },
            loc_level='state'
        )
        self.assertEquals(len(data['chart_data']), 3)

    def test_chart_data_pink(self):
        data = get_prevalence_of_undernutrition_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1)
            },
            loc_level='state'
        )
        self.assertDictEqual(
            data['chart_data'][0],
            {
                "color": ChartColors.PINK,
                "classed": "dashed",
                "strokeWidth": 2,
                "values": [
                    {
                        "y": 0.0,
                        "x": 1485907200000,
                        "all": 0,
                        "unweighed": 0
                    },
                    {
                        "y": 0.0,
                        "x": 1488326400000,
                        "all": 0,
                        "unweighed": 0
                    },
                    {
                        "y": 0.7467438494934877,
                        "x": 1491004800000,
                        "all": 3455,
                        "unweighed": 1655
                    },
                    {
                        "y": 0.7844827586206896,
                        "x": 1493596800000,
                        "all": 3480,
                        "unweighed": 1465
                    }
                ],
                "key": "% Normal"
            }
        )

    def test_chart_data_orange(self):
        data = get_prevalence_of_undernutrition_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1)
            },
            loc_level='state'
        )
        self.assertDictEqual(
            data['chart_data'][1],
            {
                "color": ChartColors.ORANGE,
                "classed": "dashed",
                "strokeWidth": 2,
                "values": [
                    {
                        "y": 0.0,
                        "x": 1485907200000,
                        "all": 0,
                        "unweighed": 0
                    },
                    {
                        "y": 0.0,
                        "x": 1488326400000,
                        "all": 0,
                        "unweighed": 0
                    },
                    {
                        "y": 0.23154848046309695,
                        "x": 1491004800000,
                        "all": 3455,
                        "unweighed": 1655
                    },
                    {
                        "y": 0.1867816091954023,
                        "x": 1493596800000,
                        "all": 3480,
                        "unweighed": 1465
                    }
                ],
                "key": "% Moderately Underweight (-2 SD)"
            }
        )

    def test_chart_data_red(self):
        data = get_prevalence_of_undernutrition_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1)
            },
            loc_level='state'
        )
        self.assertDictEqual(
            data['chart_data'][2],
            {
                "color": ChartColors.RED,
                "classed": "dashed",
                "strokeWidth": 2,
                "values": [
                    {
                        "y": 0.0,
                        "x": 1485907200000,
                        "all": 0,
                        "unweighed": 0
                    },
                    {
                        "y": 0.0,
                        "x": 1488326400000,
                        "all": 0,
                        "unweighed": 0
                    },
                    {
                        "y": 0.02170767004341534,
                        "x": 1491004800000,
                        "all": 3455,
                        "unweighed": 1655
                    },
                    {
                        "y": 0.028735632183908046,
                        "x": 1493596800000,
                        "all": 3480,
                        "unweighed": 1465
                    }
                ],
                "key": "% Severely Underweight (-3 SD) "
            }
        )

    def test_chart_data_all_locations(self):
        data = get_prevalence_of_undernutrition_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1)
            },
            loc_level='state'
        )
        self.assertListEqual(
            data['all_locations'],
            [
                {
                    "loc_name": "st2",
                    "percent": 20.58047493403694
                },
                {
                    "loc_name": "st1",
                    "percent": 22.71293375394322
                },
            ]
        )

    def test_sector_data_keys_length(self):
        data = get_prevalence_of_undernutrition_sector_data(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
            },
            location_id='b1',
            loc_level='supervisor'
        )
        self.assertEquals(len(data), 3)

    def test_sector_data_info(self):
        data = get_prevalence_of_undernutrition_sector_data(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
            },
            location_id='b1',
            loc_level='supervisor'
        )
        self.assertEquals(
            data['info'],
            "Percentage of children between 0-5 years enrolled for Anganwadi Services with weight-for-age"
            " less than -2 standard deviations of the WHO Child Growth Standards median."
            " <br/><br/>Children who are moderately "
            "or severely underweight have a higher risk of mortality"
        )

    def test_sector_data_tooltips_data(self):
        data = get_prevalence_of_undernutrition_sector_data(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
            },
            location_id='b1',
            loc_level='supervisor'
        )
        self.assertDictEqual(
            data['tooltips_data'],
            {
                u"s2": {
                    "total": 182,
                    "severely_underweight": 4,
                    "moderately_underweight": 54,
                    "normal": 124,
                    "eligible": 326
                },
                u"s1": {
                    "total": 134,
                    "severely_underweight": 8,
                    "moderately_underweight": 36,
                    "normal": 90,
                    "eligible": 144
                },
                None: {
                    "total": 158,
                    "severely_underweight": 6,
                    "moderately_underweight": 45,
                    "normal": 107,
                    "eligible": 235
                }
            }
        )

    def test_sector_data_chart_data(self):
        data = get_prevalence_of_undernutrition_sector_data(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
            },
            location_id='b1',
            loc_level='supervisor'
        )
        self.assertListEqual(
            data['chart_data'],
            [
                {
                    "color": MapColors.BLUE,
                    "classed": "dashed",
                    "strokeWidth": 2,
                    "values": [
                        [
                            None,
                            0.3227848101265823
                        ],
                        [
                            "s1",
                            0.3283582089552239
                        ],
                        [
                            "s2",
                            0.31868131868131866
                        ]
                    ],
                    "key": ""
                }
            ]
        )
