from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.prevalence_of_severe import get_prevalence_of_severe_data_map, \
    get_prevalence_of_severe_data_chart, get_prevalence_of_severe_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestPrevalenceOfSevere(TestCase):
    maxDiff = None

    def test_map_data_keys(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
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
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )['rightLegend']
        self.assertEquals(len(data), 3)
        self.assertIn('info', data)
        self.assertIn('average', data)
        self.assertIn('extended_info', data)

    def test_map_data(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertDictEqual(
            data['data'],
            {
                "st1": {
                    "severe": 0,
                    "moderate": 4,
                    "normal": 3,
                    "total_measured": 7,
                    "total": 449,
                    'original_name': ["st1"],
                    "fillKey": "7%-100%"
                },
                "st2": {
                    "severe": 0,
                    "moderate": 4,
                    "normal": 16,
                    "total_measured": 24,
                    "total": 490,
                    'original_name': ["st2"],
                    "fillKey": "7%-100%"
                }
            }
        )

    def test_map_data_right_legend_info(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        expected = (
            "Percentage of children between 6 - 60 months enrolled for Anganwadi Services with "
            "weight-for-height below -2 standard deviations of the WHO Child Growth Standards "
            "median. <br/><br/>Wasting in children is a symptom of acute undernutrition "
            "usually as a consequence of insufficient food intake or a high incidence "
            "of infectious diseases. Severe Acute Malnutrition (SAM) is nutritional "
            "status for a child who has severe wasting (weight-for-height) below -3 "
            "Z and Moderate Acute Malnutrition (MAM) is nutritional status for a child "
            "that has moderate wasting (weight-for-height) below -2Z."
        )
        self.assertEquals(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['rightLegend']['average'], "0.85")

    def test_map_data_right_legend_extended_info(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertListEqual(
            data['rightLegend']['extended_info'],
            [
                {'indicator': 'Total Children (6 - 60 months) weighed in given month:', 'value': '939'},
                {'indicator': 'Total Children (6 - 60 months) with height measured in given month:',
                 'value': '31'},
                {'indicator': 'Number of children (6 - 60 months) unmeasured:', 'value': '912'},
                {'indicator': '% Severely Acute Malnutrition (6 - 60 months):', 'value': '0.00%'},
                {'indicator': '% Moderately Acute Malnutrition (6 - 60 months):', 'value': '25.81%'},
                {'indicator': '% Normal (6 - 60 months):', 'value': '61.29%'}
            ]
        )

    def test_map_data_fills(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertDictEqual(
            data['fills'],
            {
                "0%-5%": MapColors.PINK,
                "5%-7%": MapColors.ORANGE,
                "7%-100%": MapColors.RED,
                "defaultFill": MapColors.GREY
            }
        )

    def test_map_data_slug(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['slug'], 'severe')

    def test_map_data_label(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['label'], 'Percent of Children Wasted (6 - 60 months)')

    def test_map_name_two_locations_represent_by_one_topojson(self):
        data = get_prevalence_of_severe_data_map(
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
                    'moderate': 4,
                    'total_measured': 7,
                    'normal': 3,
                    'original_name': ['b1', 'b2'],
                    'severe': 0,
                    'total': 449,
                    'fillKey': '7%-100%'
                }
            }
        )

    def test_average_with_two_locations_represent_by_one_topojson(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
        )
        self.assertEquals(data['rightLegend']['average'], "0.90")

    def test_chart_data_keys_length(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(len(data), 5)

    def test_chart_data_location_type(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['location_type'], 'State')

    def test_chart_data_bottom_five(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertListEqual(
            data['bottom_five'],
            [
                {
                    "loc_name": "st2",
                    "percent": 16.666666666666668,
                },
                {
                    "loc_name": "st1",
                    "percent": 57.142857142857146
                },
            ]
        )

    def test_chart_data_top_five(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertListEqual(
            data['top_five'],
            [
                {
                    "loc_name": "st2",
                    "percent": 16.666666666666668,
                },
                {
                    "loc_name": "st1",
                    "percent": 57.142857142857146
                },
            ]
        )

    def test_chart_data_elements_length(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(len(data['chart_data']), 3)

    def test_chart_data_pink(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
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
                        'measured': 0
                    },
                    {
                        "y": 0.0,
                        "x": 1488326400000,
                        "all": 0,
                        'measured': 0
                    },
                    {
                        "y": 0.5454545454545454,
                        "x": 1491004800000,
                        "all": 964,
                        'measured': 11
                    },
                    {
                        "y": 0.6129032258064516,
                        "x": 1493596800000,
                        "all": 939,
                        'measured': 31
                    }
                ],
                "key": "% normal"
            }
        )

    def test_chart_data_orange(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
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
                        'measured': 0
                    },
                    {
                        "y": 0.0,
                        "x": 1488326400000,
                        "all": 0,
                        'measured': 0
                    },
                    {
                        "y": 0.09090909090909091,
                        "x": 1491004800000,
                        "all": 964,
                        'measured': 11
                    },
                    {
                        "y": 0.25806451612903225,
                        "x": 1493596800000,
                        "all": 939,
                        'measured': 31
                    }
                ],
                "key": "% moderately wasted (moderate acute malnutrition)"
            }
        )

    def test_chart_data_red(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
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
                        'measured': 0
                    },
                    {
                        "y": 0.0,
                        "x": 1488326400000,
                        "all": 0,
                        'measured': 0
                    },
                    {
                        "y": 0.09090909090909091,
                        "x": 1491004800000,
                        "all": 964,
                        'measured': 11
                    },
                    {
                        "y": 0.0,
                        "x": 1493596800000,
                        "all": 939,
                        'measured': 31
                    }
                ],
                "key": "% severely wasted (severe acute malnutrition)"
            }
        )

    def test_chart_data_all_locations(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertListEqual(
            data['all_locations'],
            [
                {
                    "loc_name": "st2",
                    "percent": 16.666666666666668,
                },
                {
                    "loc_name": "st1",
                    "percent": 57.142857142857146
                },
            ]
        )

    def test_sector_data_keys_length(self):
        data = get_prevalence_of_severe_sector_data(
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
        )
        self.assertEquals(len(data), 3)

    def test_sector_data_info(self):
        data = get_prevalence_of_severe_sector_data(
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
        )
        self.assertEquals(
            data['info'],
            "Percentage of children between 6 - 60 months enrolled for Anganwadi Services with "
            "weight-for-height below -3 standard deviations of the WHO Child Growth Standards"
            " median.<br/><br/>Severe Acute Malnutrition (SAM) or wasting in"
            " children is a symptom of acute undernutrition usually as "
            "a consequence of insufficient food intake or a high incidence of infectious diseases."
        )

    def test_sector_data_tooltips_data(self):
        data = get_prevalence_of_severe_sector_data(
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
        )
        self.assertDictEqual(
            data['tooltips_data'],
            {
                "s2": {
                    "total": 150,
                    "severe": 0,
                    "moderate": 3,
                    "total_measured": 4,
                    "normal": 1
                },
                "s1": {
                    "total": 70,
                    "severe": 0,
                    "moderate": 0,
                    "total_measured": 0,
                    "normal": 0
                }
            }
        )

    def test_sector_data_chart_data(self):
        data = get_prevalence_of_severe_sector_data(
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
                            "s1",
                            0.0
                        ],
                        [
                            "s2",
                            0.02
                        ]
                    ],
                    "key": ""
                }
            ]
        )
