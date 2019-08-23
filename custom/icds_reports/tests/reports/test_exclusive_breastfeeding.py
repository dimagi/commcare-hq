from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.messages import exclusive_breastfeeding_help_text
from custom.icds_reports.reports.exclusive_breastfeeding import get_exclusive_breastfeeding_data_map, \
    get_exclusive_breastfeeding_data_chart, get_exclusive_breastfeeding_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestExclusiveBreastfeeding(TestCase):

    def test_map_data_keys(self):
        data = get_exclusive_breastfeeding_data_map(
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
        data = get_exclusive_breastfeeding_data_map(
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
        data = get_exclusive_breastfeeding_data_map(
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
                'st4': {'all': 0, 'original_name': ['st4'], 'children': 0, 'fillKey': '0%-20%'},
                'st5': {'all': 0, 'original_name': ['st5'], 'children': 0, 'fillKey': '0%-20%'},
                'st6': {'all': 0, 'original_name': ['st6'], 'children': 0, 'fillKey': '0%-20%'},
                'st7': {'all': 0, 'original_name': ['st7'], 'children': 0, 'fillKey': '0%-20%'},
                'st1': {'all': 26, 'original_name': ['st1'], 'children': 17, 'fillKey': '60%-100%'},
                'st2': {'all': 24, 'original_name': ['st2'], 'children': 11, 'fillKey': '20%-60%'},
                'st3': {'all': 0, 'original_name': ['st3'], 'children': 0, 'fillKey': '0%-20%'}
            }
        )

    def test_map_data_right_legend_info(self):
        data = get_exclusive_breastfeeding_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        expected = exclusive_breastfeeding_help_text(html=True)
        self.assertEquals(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_exclusive_breastfeeding_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['rightLegend']['average'], 56.0)

    def test_map_data_right_legend_extended_info(self):
        data = get_exclusive_breastfeeding_data_map(
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
                {
                    'indicator': 'Total number of children between ages 0 - 6 months:',
                    'value': "50"
                },
                {
                    'indicator': (
                        'Total number of children (0-6 months) exclusively breastfed in the given month:'
                    ),
                    'value': "28"
                },
                {
                    'indicator': '% children (0-6 months) exclusively breastfed in the given month:',
                    'value': '56.00%'
                }
            ]
        )

    def test_map_data_fills(self):
        data = get_exclusive_breastfeeding_data_map(
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
                "0%-20%": MapColors.RED,
                "20%-60%": MapColors.ORANGE,
                "60%-100%": MapColors.PINK,
                "defaultFill": MapColors.GREY
            }
        )

    def test_map_data_slug(self):
        data = get_exclusive_breastfeeding_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['slug'], 'severe')

    def test_map_data_label(self):
        data = get_exclusive_breastfeeding_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['label'], 'Percent Exclusive Breastfeeding')

    def test_map_name_two_locations_represent_by_one_topojson(self):
        data = get_exclusive_breastfeeding_data_map(
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
                    'all': 26,
                    'original_name': ['b1', 'b2'],
                    'children': 17,
                    'fillKey': '60%-100%'
                }
            }
        )

    def test_average_with_two_locations_represent_by_one_topojson(self):
        data = get_exclusive_breastfeeding_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
        )
        self.assertEquals(data['rightLegend']['average'], 65.38461538461539)

    def test_chart_data(self):
        self.assertDictEqual(
            get_exclusive_breastfeeding_data_chart(
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
                    {'loc_name': 'st3', 'percent': 0.0},
                    {'loc_name': 'st4', 'percent': 0.0},
                    {'loc_name': 'st5', 'percent': 0.0},
                    {'loc_name': 'st6', 'percent': 0.0},
                    {'loc_name': 'st7', 'percent': 0.0},
                ],
                "top_five": [
                    {'loc_name': 'st1', 'percent': 65.38461538461539},
                    {'loc_name': 'st2', 'percent': 45.833333333333336},
                    {'loc_name': 'st3', 'percent': 0.0},
                    {'loc_name': 'st4', 'percent': 0.0},
                    {'loc_name': 'st5', 'percent': 0.0},
                ],
                "chart_data": [
                    {
                        "color": ChartColors.BLUE,
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            {
                                "y": 0,
                                "x": 1485907200000,
                                "all": 0,
                                "in_month": 0
                            },
                            {
                                "y": 0,
                                "x": 1488326400000,
                                "all": 0,
                                "in_month": 0
                            },
                            {
                                "y": 0.22413793103448276,
                                "x": 1491004800000,
                                "all": 58,
                                "in_month": 13
                            },
                            {
                                "y": 0.56,
                                "x": 1493596800000,
                                "all": 50,
                                "in_month": 28
                            }
                        ],
                        "key": "% children exclusively breastfed"
                    }
                ],
                "all_locations": [
                    {'loc_name': 'st1', 'percent': 65.38461538461539},
                    {'loc_name': 'st2', 'percent': 45.833333333333336},
                    {'loc_name': 'st3', 'percent': 0.0},
                    {'loc_name': 'st4', 'percent': 0.0},
                    {'loc_name': 'st5', 'percent': 0.0},
                    {'loc_name': 'st6', 'percent': 0.0},
                    {'loc_name': 'st7', 'percent': 0.0},
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_exclusive_breastfeeding_sector_data(
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
                "info": exclusive_breastfeeding_help_text(html=True),
                "tooltips_data": {
                    "s2": {
                        "all": 13,
                        "children": 7
                    },
                    "s1": {
                        "all": 2,
                        "children": 0
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
                                0.5384615384615384
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
