from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.messages import percent_aadhaar_seeded_beneficiaries_help_text
from custom.icds_reports.reports.adhaar import get_adhaar_data_map, get_adhaar_data_chart, get_adhaar_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestAdhaar(TestCase):

    def test_map_data_keys(self):
        data = get_adhaar_data_map(
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
        data = get_adhaar_data_map(
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
        data = get_adhaar_data_map(
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
                 'st4': {'in_month': 0, 'original_name': ['st4'], 'all': 0, 'fillKey': '0%-25%'},
                 'st5': {'in_month': 0, 'original_name': ['st5'], 'all': 0, 'fillKey': '0%-25%'},
                 'st6': {'in_month': 0, 'original_name': ['st6'], 'all': 0, 'fillKey': '0%-25%'},
                 'st7': {'in_month': 0, 'original_name': ['st7'], 'all': 2, 'fillKey': '0%-25%'},
                 'st1': {'in_month': 192, 'original_name': ['st1'], 'all': 775, 'fillKey': '0%-25%'},
                 'st2': {'in_month': 154, 'original_name': ['st2'], 'all': 833, 'fillKey': '0%-25%'},
                 'st3': {'in_month': 0, 'original_name': ['st3'], 'all': 0, 'fillKey': '0%-25%'}
            }
        )

    def test_map_data_right_legend_info(self):
        data = get_adhaar_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        expected = percent_aadhaar_seeded_beneficiaries_help_text()
        self.assertEqual(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_adhaar_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(data['rightLegend']['average'], 21.490683229813666)

    def test_map_data_right_legend_extended_info(self):
        data = get_adhaar_data_map(
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
                    'indicator': 'Total number of ICDS beneficiaries whose Aadhaar has been captured:',
                    'value': "346"
                },
                {
                    'indicator': '% of ICDS beneficiaries whose Aadhaar has been captured:',
                    'value': '21.49%'
                }
            ]
        )

    def test_map_data_fills(self):
        data = get_adhaar_data_map(
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
                "0%-25%": MapColors.RED,
                "25%-50%": MapColors.ORANGE,
                "50%-100%": MapColors.PINK,
                "defaultFill": MapColors.GREY
            }
        )

    def test_map_data_slug(self):
        data = get_adhaar_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['slug'], 'adhaar')

    def test_map_data_label(self):
        data = get_adhaar_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['label'], 'Percent Aadhaar-seeded Beneficiaries')

    def test_map_name_two_locations_represent_by_one_topojson(self):
        data = get_adhaar_data_map(
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
                    'in_month': 192,
                    'original_name': ['b1', 'b2'],
                    'all': 775,
                    'fillKey': '0%-25%'
                }
            }
        )

    def test_average_with_two_locations_represent_by_one_topojson(self):
        data = get_adhaar_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
        )
        self.assertEqual(data['rightLegend']['average'], 24.774193548387096)

    def test_chart_data(self):
        self.assertDictEqual(
            get_adhaar_data_chart(
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
                    {'loc_name': 'st1', 'percent': 24.774193548387096},
                    {'loc_name': 'st2', 'percent': 18.48739495798319},
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
                                "y": 0.19528178243774574,
                                "x": 1491004800000,
                                "all": 1526
                            },
                            {
                                "y": 0.21490683229813665,
                                "x": 1493596800000,
                                "all": 1610
                            }
                        ],
                        "key": "Percentage of beneficiaries with Aadhaar numbers"
                    }
                ],
                "all_locations": [
                    {'loc_name': 'st1', 'percent': 24.774193548387096},
                    {'loc_name': 'st2', 'percent': 18.48739495798319},
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
            get_adhaar_sector_data(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'aggregation_level': 4
                },
                loc_level='supervisor',
                location_id='b1'
            ),
            {
                "info": percent_aadhaar_seeded_beneficiaries_help_text(),
                "tooltips_data": {
                    "s2": {
                        "in_month": 51,
                        "all": 262
                    },
                    "s1": {
                        "in_month": 72,
                        "all": 139
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
                                0.5179856115107914
                            ],
                            [
                                "s2",
                                0.1946564885496183
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
