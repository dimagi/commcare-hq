from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.prevalence_of_stunting import get_prevalence_of_stunting_data_map, \
    get_prevalence_of_stunting_data_chart, get_prevalence_of_stunting_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds-new')
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
        self.assertEquals(len(data), 5)
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
        self.assertEquals(len(data), 3)
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
                "st1": {
                    "severe": 2,
                    "moderate": 3,
                    "normal": 2,
                    "total_measured": 7,
                    "total": 449,
                    'original_name': ["st1"],
                    "fillKey": "38%-100%"
                },
                "st2": {
                    "severe": 9,
                    "moderate": 5,
                    "normal": 11,
                    "total_measured": 25,
                    "total": 490,
                    'original_name': ["st2"],
                    "fillKey": "38%-100%"
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
            "Percentage of children (6 - 60 months) enrolled for Anganwadi Services with "
            "height-for-age below -2Z standard deviations of "
            "the WHO Child Growth Standards median.<br/><br/>Stunting "
            "is a sign of chronic undernutrition and has long "
            "lasting harmful consequences on the growth of a child"
        )
        self.assertEquals(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_prevalence_of_stunting_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['rightLegend']['average'], "63.71")

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
                {'indicator': 'Total Children (6 - 60 months) eligible to have height measured:', 'value': '939'},
                {'indicator': 'Total Children (6 - 60 months) with height measured in given month:',
                 'value': '32'},
                {'indicator': 'Number of Children (6 - 60 months) unmeasured:', 'value': '907'},
                {'indicator': '% children (6 - 60 months) with severely stunted growth:', 'value': '34.38%'},
                {'indicator': '% children (6 - 60 months) with moderate stunted growth:', 'value': '25.00%'},
                {'indicator': '% children (6 - 60 months) with normal stunted growth:', 'value': '40.62%'}
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
        self.assertEquals(data['slug'], 'severe')

    def test_map_data_label(self):
        data = get_prevalence_of_stunting_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['label'], 'Percent of Children Stunted (6 - 60 months)')

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
                    'total': 449,
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
        self.assertEquals(data['rightLegend']['average'], "75.00")

    def test_chart_data_keys_length(self):
        data = get_prevalence_of_stunting_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(len(data), 5)

    def test_chart_data_location_type(self):
        data = get_prevalence_of_stunting_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['location_type'], 'State')

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
                {
                    "loc_name": "st2",
                    "percent": 56.0
                },
                {
                    "loc_name": "st1",
                    "percent": 71.42857142857143
                },
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
                {
                    "loc_name": "st2",
                    "percent": 56.0
                },
                {
                    "loc_name": "st1",
                    "percent": 71.42857142857143
                },
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
        self.assertEquals(len(data['chart_data']), 3)

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
                        "y": 0.18181818181818182,
                        "x": 1491004800000,
                        "all": 964,
                        "measured": 11
                    },
                    {
                        "y": 0.40625,
                        "x": 1493596800000,
                        "all": 939,
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
                        "y": 0.36363636363636365,
                        "x": 1491004800000,
                        "all": 964,
                        "measured": 11
                    },
                    {
                        "y": 0.25,
                        "x": 1493596800000,
                        "all": 939,
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
                        "y": 0.45454545454545453,
                        "x": 1491004800000,
                        "all": 964,
                        "measured": 11
                    },
                    {
                        "y": 0.34375,
                        "x": 1493596800000,
                        "all": 939,
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
                {
                    "loc_name": "st2",
                    "percent": 56.0
                },
                {
                    "loc_name": "st1",
                    "percent": 71.42857142857143
                },
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
        self.assertEquals(len(data), 3)

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
        self.assertEquals(
            data['info'],
            "Percentage of children (6 - 60 months) enrolled for Anganwadi Services with height-for-age below"
            " -2Z standard deviations of the WHO Child Growth Standards median."
            "<br/><br/>Stunting is a sign of chronic undernutrition "
            "and has long lasting harmful consequences on the growth of a child"
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
