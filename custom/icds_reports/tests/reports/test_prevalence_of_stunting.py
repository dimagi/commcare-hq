from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.prevalence_of_stunting import get_prevalence_of_stunting_data_map, \
    get_prevalence_of_stunting_data_chart, get_prevalence_of_stunting_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestPrevalenceOfStunting(TestCase):
    maxDiff = None

    def test_map_data_keys(self):
        data = get_prevalence_of_stunting_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(len(data), 5)
        self.assertIn('rightLegend', data)
        self.assertIn('fills', data)
        self.assertIn('data', data)
        self.assertIn('slug', data)
        self.assertIn('label', data)

    def test_map_data_right_legend_keys(self):
        data = get_prevalence_of_stunting_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )['rightLegend']
        self.assertEqual(len(data), 3)
        self.assertIn('info', data)
        self.assertIn('average', data)
        self.assertIn('extended_info', data)

    def test_map_data(self):
        data = get_prevalence_of_stunting_data_map(
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
                'st4': {
                    'moderate': 0,
                    'normal': 0,
                    'total_measured': 0,
                    'original_name': ['st4'],
                    'severe': 0,
                    'total': 0,
                    'fillKey': '0%-25%'
                },
                'st5': {
                    'moderate': 0,
                    'normal': 0,
                    'total_measured': 0,
                    'original_name': ['st5'],
                    'severe': 0,
                    'total': 0,
                    'fillKey': '0%-25%'
                },
                'st6': {
                    'moderate': 0,
                    'normal': 0,
                    'total_measured': 0,
                    'original_name': ['st6'],
                    'severe': 0,
                    'total': 0,
                    'fillKey': '0%-25%'
                },
                'st7': {
                    'moderate': 0,
                    'normal': 0,
                    'total_measured': 0,
                    'original_name': ['st7'],
                    'severe': 0,
                    'total': 1,
                    'fillKey': '0%-25%'
                },
                'st1': {
                    'moderate': 3,
                    'normal': 2,
                    'total_measured': 7,
                    'original_name': ['st1'],
                    'severe': 2,
                    'total': 454,
                    'fillKey': '38%-100%'
                },
                'st2': {
                    'moderate': 5,
                    'normal': 11,
                    'total_measured': 25,
                    'original_name': ['st2'],
                    'severe': 9,
                    'total': 497,
                    'fillKey': '38%-100%'
                },
                'st3': {
                    'moderate': 0,
                    'normal': 0,
                    'total_measured': 0,
                    'original_name': ['st3'],
                    'severe': 0,
                    'total': 0,
                    'fillKey': '0%-25%'
                }
            }
        )

    def test_map_data_right_legend_info(self):
        data = get_prevalence_of_stunting_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        expected = (
            "Of the children enrolled for Anganwadi services, whose height was measured, the percentage of "
            "children between 0 - 5 years who were moderately/severely stunted in the current month. "
            "<br/><br/>"
            "Stunting is a sign of chronic undernutrition and has long lasting harmful consequences "
            "on the growth of a child"
        )
        self.assertEqual(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_prevalence_of_stunting_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(data['rightLegend']['average'], "59.38")

    def test_map_data_right_legend_extended_info(self):
        data = get_prevalence_of_stunting_data_map(
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
                {'indicator': 'Total Children (0 - 5 years) eligible to have height measured:', 'value': '952'},
                {'indicator': 'Total Children (0 - 5 years) with height measured in given month:',
                 'value': '32'},
                {'indicator': 'Number of Children (0 - 5 years) unmeasured:', 'value': '920'},
                {'indicator': '% children (0 - 5 years) with severely stunted growth:', 'value': '34.38%'},
                {'indicator': '% children (0 - 5 years) with moderate stunted growth:', 'value': '25.00%'},
                {'indicator': '% children (0 - 5 years) with normal stunted growth:', 'value': '40.62%'}
            ]
        )

    def test_map_data_fills(self):
        data = get_prevalence_of_stunting_data_map(
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
                "0%-25%": MapColors.PINK,
                "25%-38%": MapColors.ORANGE,
                "38%-100%": MapColors.RED,
                "defaultFill": MapColors.GREY
            }
        )

    def test_map_data_slug(self):
        data = get_prevalence_of_stunting_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(data['slug'], 'severe')

    def test_map_data_label(self):
        data = get_prevalence_of_stunting_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(data['label'], 'Percent of Children Stunted (0 - 5 years)')

    def test_map_name_two_locations_represent_by_one_topojson(self):
        data = get_prevalence_of_stunting_data_map(
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
                    'moderate': 3,
                    'total_measured': 7,
                    'normal': 2,
                    'original_name': ['b1', 'b2'],
                    'severe': 2,
                    'total': 454,
                    'fillKey': '38%-100%'
                }
            }
        )

    def test_average_with_two_locations_represent_by_one_topojson(self):
        data = get_prevalence_of_stunting_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
        )
        self.assertEqual(data['rightLegend']['average'], "71.43")

    def test_chart_data_keys_length(self):
        data = get_prevalence_of_stunting_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(len(data), 5)

    def test_chart_data_location_type(self):
        data = get_prevalence_of_stunting_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(data['location_type'], 'State')

    def test_chart_data_bottom_five(self):
        data = get_prevalence_of_stunting_data_chart(
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
                {'loc_name': 'st5', 'percent': 0.0},
                {'loc_name': 'st6', 'percent': 0.0},
                {'loc_name': 'st7', 'percent': 0.0},
                {'loc_name': 'st2', 'percent': 56.0},
                {'loc_name': 'st1', 'percent': 71.42857142857143}
            ]
        )

    def test_chart_data_top_five(self):
        data = get_prevalence_of_stunting_data_chart(
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
                {'loc_name': 'st3', 'percent': 0.0},
                {'loc_name': 'st4', 'percent': 0.0},
                {'loc_name': 'st5', 'percent': 0.0},
                {'loc_name': 'st6', 'percent': 0.0},
                {'loc_name': 'st7', 'percent': 0.0}
            ]
        )

    def test_chart_data_elements_length(self):
        data = get_prevalence_of_stunting_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(len(data['chart_data']), 3)

    def test_chart_data_pink(self):
        data = get_prevalence_of_stunting_data_chart(
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
                        "measured": 0
                    },
                    {
                        "y": 0.0,
                        "x": 1488326400000,
                        "all": 0,
                        "measured": 0
                    },
                    {
                        "y": 0.3076923076923077,
                        "x": 1491004800000,
                        "all": 981,
                        "measured": 13
                    },
                    {
                        "y": 0.40625,
                        "x": 1493596800000,
                        "all": 952,
                        "measured": 32
                    }
                ],
                "key": "% normal"
            }
        )

    def test_chart_data_orange(self):
        data = get_prevalence_of_stunting_data_chart(
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
                        "measured": 0
                    },
                    {
                        "y": 0.0,
                        "x": 1488326400000,
                        "all": 0,
                        "measured": 0
                    },
                    {
                        "y": 0.3076923076923077,
                        "x": 1491004800000,
                        "all": 981,
                        "measured": 13
                    },
                    {
                        "y": 0.25,
                        "x": 1493596800000,
                        "all": 952,
                        "measured": 32
                    }
                ],
                "key": "% moderately stunted"
            }
        )

    def test_chart_data_red(self):
        data = get_prevalence_of_stunting_data_chart(
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
                        "measured": 0
                    },
                    {
                        "y": 0.0,
                        "x": 1488326400000,
                        "all": 0,
                        "measured": 0
                    },
                    {
                        "y": 0.38461538461538464,
                        "x": 1491004800000,
                        "all": 981,
                        "measured": 13
                    },
                    {
                        "y": 0.34375,
                        "x": 1493596800000,
                        "all": 952,
                        "measured": 32
                    }
                ],
                "key": "% severely stunted"
            }
        )

    def test_chart_data_all_locations(self):
        data = get_prevalence_of_stunting_data_chart(
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
                {'loc_name': 'st3', 'percent': 0.0},
                {'loc_name': 'st4', 'percent': 0.0},
                {'loc_name': 'st5', 'percent': 0.0},
                {'loc_name': 'st6', 'percent': 0.0},
                {'loc_name': 'st7', 'percent': 0.0},
                {'loc_name': 'st2', 'percent': 56.0},
                {'loc_name': 'st1', 'percent': 71.42857142857143}
            ]
        )

    def test_sector_data_keys_length(self):
        data = get_prevalence_of_stunting_sector_data(
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
        self.assertEqual(len(data), 3)

    def test_sector_data_info(self):
        data = get_prevalence_of_stunting_sector_data(
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
        self.assertEqual(
            data['info'],
            "Of the children enrolled for Anganwadi services, whose height was measured, the percentage of "
            "children between  (0 - 5 years) who were moderately/severely stunted in the current month. "
            "<br/><br/>"
            "Stunting is a sign of chronic undernutrition and has long lasting harmful "
            "consequences on the growth of a child"
        )

    def test_sector_data_tooltips_data(self):
        data = get_prevalence_of_stunting_sector_data(
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
                    "total": 153,
                    "severe": 0,
                    "moderate": 2,
                    "total_measured": 4,
                    "normal": 2
                },
                "s1": {
                    "total": 71,
                    "severe": 0,
                    "moderate": 0,
                    "total_measured": 0,
                    "normal": 0
                }
            }
        )

    def test_sector_data_chart_data(self):
        data = get_prevalence_of_stunting_sector_data(
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
                            0.5
                        ]
                    ],
                    "key": ""
                }
            ]
        )
