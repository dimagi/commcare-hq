from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.new_born_with_low_weight import get_newborn_with_low_birth_weight_map, \
    get_newborn_with_low_birth_weight_chart, get_newborn_with_low_birth_weight_data
from django.test import TestCase

from custom.icds_reports.messages import new_born_with_low_weight_help_text


@override_settings(SERVER_ENVIRONMENT='icds-new')
class TestNewBornWithLowWeight(TestCase):

    def test_map_data_keys(self):
        data = get_newborn_with_low_birth_weight_map(
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
        data = get_newborn_with_low_birth_weight_map(
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
        data = get_newborn_with_low_birth_weight_map(
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
                'st4': {'in_month': 0, 'original_name': ['st4'], 'low_birth': 0, 'all': 0, 'fillKey': '0%-20%'},
                'st5': {'in_month': 0, 'original_name': ['st5'], 'low_birth': 0, 'all': 0, 'fillKey': '0%-20%'},
                'st6': {'in_month': 0, 'original_name': ['st6'], 'low_birth': 0, 'all': 0, 'fillKey': '0%-20%'},
                'st7': {'in_month': 0, 'original_name': ['st7'], 'low_birth': 0, 'all': 0, 'fillKey': '0%-20%'},
                'st1': {'in_month': 2, 'original_name': ['st1'], 'low_birth': 1, 'all': 2, 'fillKey': '20%-60%'},
                'st2': {'in_month': 1, 'original_name': ['st2'], 'low_birth': 0, 'all': 3, 'fillKey': '0%-20%'},
                'st3': {'in_month': 0, 'original_name': ['st3'], 'low_birth': 0, 'all': 0, 'fillKey': '0%-20%'}
            }
        )

    def test_map_data_right_legend_info(self):
        data = get_newborn_with_low_birth_weight_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        expected = (
            new_born_with_low_weight_help_text(html=True)
        )
        self.assertEquals(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_newborn_with_low_birth_weight_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['rightLegend']['average'], 33.333333333333336)

    def test_map_data_right_legend_extended_info(self):
        data = get_newborn_with_low_birth_weight_map(
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
                {'indicator': 'Total Number of Newborns born in given month:', 'value': "5"},
                {'indicator': 'Number of Newborns with LBW in given month:', 'value': "1"},
                {'indicator': 'Total Number of children born and weight in given month:', 'value': '3'},
                {'indicator': '% newborns with LBW in given month:', 'value': '33.33%'},
                {'indicator': '% of children with weight in normal:', 'value': '66.67%'},
                {'indicator': '% Unweighted:', 'value': '40.00%'},
            ]
        )

    def test_map_data_fills(self):
        data = get_newborn_with_low_birth_weight_map(
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
                "0%-20%": MapColors.PINK,
                "20%-60%": MapColors.ORANGE,
                "60%-100%": MapColors.RED,
                "defaultFill": MapColors.GREY
            }
        )

    def test_map_data_slug(self):
        data = get_newborn_with_low_birth_weight_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['slug'], 'low_birth')

    def test_map_data_label(self):
        data = get_newborn_with_low_birth_weight_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['label'], 'Percent Newborns with Low Birth Weight')

    def test_map_name_two_locations_represent_by_one_topojson(self):
        data = get_newborn_with_low_birth_weight_map(
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
                    'in_month': 2,
                    'original_name': ['b1', 'b2'],
                    'low_birth': 1,
                    'all': 2,
                    'fillKey': '20%-60%'
                }
            }
        )

    def test_average_with_two_locations_represent_by_one_topojson(self):
        data = get_newborn_with_low_birth_weight_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
        )
        self.assertEquals(data['rightLegend']['average'], 50.0)

    def test_chart_data_keys_length(self):
        data = get_newborn_with_low_birth_weight_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(len(data), 5)

    def test_chart_data_location_type(self):
        data = get_newborn_with_low_birth_weight_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['location_type'], 'State')

    def test_chart_data_bottom_five(self):
        data = get_newborn_with_low_birth_weight_chart(
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
                {'loc_name': 'st4', 'percent': 0.0},
                {'loc_name': 'st5', 'percent': 0.0},
                {'loc_name': 'st6', 'percent': 0.0},
                {'loc_name': 'st7', 'percent': 0.0},
                {'loc_name': 'st1', 'percent': 50.0}
            ]
        )

    def test_chart_data_top_five(self):
        data = get_newborn_with_low_birth_weight_chart(
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
                {'loc_name': 'st2', 'percent': 0.0},
                {'loc_name': 'st3', 'percent': 0.0},
                {'loc_name': 'st4', 'percent': 0.0},
                {'loc_name': 'st5', 'percent': 0.0},
                {'loc_name': 'st6', 'percent': 0.0},
            ]
        )

    def test_chart_data_elements_length(self):
        data = get_newborn_with_low_birth_weight_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(len(data['chart_data']), 1)

    def test_chart_data(self):
        data = get_newborn_with_low_birth_weight_chart(
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
                "color": ChartColors.BLUE,
                "classed": "dashed",
                "strokeWidth": 2,
                "values": [
                    {
                        "y": 0,
                        "x": 1485907200000,
                        "in_month": 0,
                        "low_birth": 0,
                        "all": 0},
                    {
                        "y": 0,
                        "x": 1488326400000,
                        "in_month": 0,
                        "low_birth": 0,
                        "all": 0},
                    {
                        "y": 0.0,
                        "x": 1491004800000,
                        "in_month": 3,
                        "low_birth": 0,
                        "all": 6},
                    {
                        "y": 0.3333333333333333,
                        "x": 1493596800000,
                        "in_month": 3,
                        "low_birth": 1,
                        "all": 5
                    }
                ],
                "key": "% Newborns with Low Birth Weight"
            }
        )

    def test_chart_data_all_locations(self):
        data = get_newborn_with_low_birth_weight_chart(
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
                {'loc_name': 'st2', 'percent': 0.0},
                {'loc_name': 'st3', 'percent': 0.0},
                {'loc_name': 'st4', 'percent': 0.0},
                {'loc_name': 'st5', 'percent': 0.0},
                {'loc_name': 'st6', 'percent': 0.0},
                {'loc_name': 'st7', 'percent': 0.0},
                {'loc_name': 'st1', 'percent': 50.0}
            ]
        )
    
    def test_sector_data_keys_length(self):
        data = get_newborn_with_low_birth_weight_data(
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
        data = get_newborn_with_low_birth_weight_data(
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
            new_born_with_low_weight_help_text(html=True)
        )

    def test_sector_data_tooltips_data(self):
        data = get_newborn_with_low_birth_weight_data(
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
                    "in_month": 0,
                    "low_birth": 0,
                    "all": 0
                },
                "s1": {
                    "in_month": 1,
                    "low_birth": 1,
                    "all": 1
                }
            }
        )

    def test_sector_data_chart_data(self):
        data = get_newborn_with_low_birth_weight_data(
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
                            1.0
                        ],
                        [
                            "s2",
                            0.0
                        ]
                    ],
                    "key": ""
                }
            ]
        )
