from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.messages import early_initiation_breastfeeding_help_text
from custom.icds_reports.reports.early_initiation_breastfeeding import get_early_initiation_breastfeeding_map, \
    get_early_initiation_breastfeeding_chart, get_early_initiation_breastfeeding_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestEarlyInitiationBreastFeeding(TestCase):

    def test_map_data_keys(self):
        data = get_early_initiation_breastfeeding_map(
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
        data = get_early_initiation_breastfeeding_map(
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
        data = get_early_initiation_breastfeeding_map(
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
                'st4': {'in_month': 0, 'original_name': ['st4'], 'birth': 0, 'fillKey': '0%-20%'},
                'st5': {'in_month': 0, 'original_name': ['st5'], 'birth': 0, 'fillKey': '0%-20%'},
                'st6': {'in_month': 0, 'original_name': ['st6'], 'birth': 0, 'fillKey': '0%-20%'},
                'st7': {'in_month': 0, 'original_name': ['st7'], 'birth': 0, 'fillKey': '0%-20%'},
                'st1': {'in_month': 2, 'original_name': ['st1'], 'birth': 1, 'fillKey': '20%-60%'},
                'st2': {'in_month': 3, 'original_name': ['st2'], 'birth': 1, 'fillKey': '20%-60%'},
                'st3': {'in_month': 0, 'original_name': ['st3'], 'birth': 0, 'fillKey': '0%-20%'}
            }
        )

    def test_map_data_right_legend_info(self):
        data = get_early_initiation_breastfeeding_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        expected = early_initiation_breastfeeding_help_text(html=True)
        self.assertEquals(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_early_initiation_breastfeeding_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['rightLegend']['average'], 40.0)

    def test_map_data_right_legend_extended_info(self):
        data = get_early_initiation_breastfeeding_map(
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
                {'indicator': 'Total Number of Children born in the given month:', 'value': "5"},
                {
                    'indicator': (
                        'Total Number of Children who were put to the breast within one hour of birth:'
                    ),
                    'value': "2"
                },
                {
                    'indicator': '% children who were put to the breast within one hour of birth:',
                    'value': '40.00%'
                }
            ]
        )

    def test_map_data_fills(self):
        data = get_early_initiation_breastfeeding_map(
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
        data = get_early_initiation_breastfeeding_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['slug'], 'early_initiation')

    def test_map_data_label(self):
        data = get_early_initiation_breastfeeding_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['label'], 'Percent Early Initiation of Breastfeeding')

    def test_map_name_two_locations_represent_by_one_topojson(self):
        data = get_early_initiation_breastfeeding_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 1
            },
            loc_level='block',
        )
        self.assertDictEqual(
            data['data'],
            {}
        )

    def test_average_with_two_locations_represent_by_one_topojson(self):
        data = get_early_initiation_breastfeeding_map(
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

    def test_chart_data(self):
        self.assertDictEqual(
            get_early_initiation_breastfeeding_chart(
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
                    {'loc_name': 'st1', 'percent': 50.0},
                    {'loc_name': 'st2', 'percent': 33.333333333333336},
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
                                "birth": 0
                            },
                            {
                                "y": 0,
                                "x": 1488326400000,
                                "all": 0,
                                "birth": 0
                            },
                            {
                                "y": 0.3333333333333333,
                                "x": 1491004800000,
                                "all": 6,
                                "birth": 2
                            },
                            {
                                "y": 0.4,
                                "x": 1493596800000,
                                "all": 5,
                                "birth": 2
                            }
                        ],
                        "key": "% Early Initiation of Breastfeeding"
                    }
                ],
                "all_locations": [
                    {'loc_name': 'st1', 'percent': 50.0},
                    {'loc_name': 'st2', 'percent': 33.333333333333336},
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
            get_early_initiation_breastfeeding_data(
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
                "info": early_initiation_breastfeeding_help_text(html=True),
                "tooltips_data": {
                    "s2": {
                        "in_month": 0,
                        "birth": 0
                    },
                    "s1": {
                        "in_month": 1,
                        "birth": 0
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
                                0.0
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
