from __future__ import absolute_import

from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.messages import awcs_reported_medicine_kit_help_text
from custom.icds_reports.reports.medicine_kit import get_medicine_kit_data_map, get_medicine_kit_data_chart, \
    get_medicine_kit_sector_data
from django.test import TestCase
from custom.icds_reports.const import ChartColors, MapColors


@override_settings(SERVER_ENVIRONMENT='icds-new')
class TestMedicineKit(TestCase):

    def test_map_data_keys(self):
        data = get_medicine_kit_data_map(
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
        data = get_medicine_kit_data_map(
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
        data = get_medicine_kit_data_map(
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
                'st7': {'in_month': 0, 'original_name': ['st7'], 'all': 0, 'fillKey': '0%-25%'},
                'st1': {'in_month': 9, 'original_name': ['st1'], 'all': 17, 'fillKey': '25%-75%'},
                'st2': {'in_month': 11, 'original_name': ['st2'], 'all': 13, 'fillKey': '75%-100%'},
                'st3': {'in_month': 0, 'original_name': ['st3'], 'all': 0, 'fillKey': '0%-25%'}
            }
        )

    def test_map_data_right_legend_info(self):
        data = get_medicine_kit_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        expected = awcs_reported_medicine_kit_help_text()
        self.assertEquals(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_medicine_kit_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['rightLegend']['average'], 66.66666666666667)

    def test_map_data_right_legend_extended_info(self):
        data = get_medicine_kit_data_map(
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
                {'indicator': 'Total number of AWCs with a Medicine Kit:', 'value': "20"},
                {'indicator': '% of AWCs with a Medicine Kit:', 'value': '66.67%'}
            ]
        )

    def test_map_data_fills(self):
        data = get_medicine_kit_data_map(
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
                "25%-75%": MapColors.ORANGE,
                "75%-100%": MapColors.PINK,
                "defaultFill": MapColors.GREY
            }
        )

    def test_map_data_slug(self):
        data = get_medicine_kit_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['slug'], 'medicine_kit')

    def test_map_data_label(self):
        data = get_medicine_kit_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['label'], 'Percentage of AWCs that reported having a Medicine Kit')

    def test_map_name_two_locations_represent_by_one_topojson(self):
        data = get_medicine_kit_data_map(
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
                "block_map": {
                    "in_month": 9,
                    "original_name": [
                        "b1",
                        "b2"
                    ],
                    "all": 17,
                    "fillKey": "25%-75%"
                }
            }
        )

    def test_average_with_two_locations_represent_by_one_topojson(self):
        data = get_medicine_kit_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
        )
        self.assertEquals(data['rightLegend']['average'], 52.94117647058823)

    def test_chart_data_keys(self):
        data = get_medicine_kit_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(len(data), 5)
        self.assertIn('top_five', data)
        self.assertIn('bottom_five', data)
        self.assertIn('all_locations', data)
        self.assertIn('chart_data', data)
        self.assertIn('location_type', data)

    def test_chart_data(self):
        data = get_medicine_kit_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertListEqual(
            data['chart_data'],
            [
                {
                    "color": ChartColors.BLUE,
                    "classed": "dashed",
                    "strokeWidth": 2,
                    "values": [
                        {
                            "y": 0.0,
                            "x": 1485907200000,
                            "in_month": 0
                        },
                        {
                            "y": 0.0,
                            "x": 1488326400000,
                            "in_month": 0
                        },
                        {
                            "y": 0.7857142857142857,
                            "x": 1491004800000,
                            "in_month": 11
                        },
                        {
                            "y": 0.6666666666666666,
                            "x": 1493596800000,
                            "in_month": 20
                        }
                    ],
                    "key": "Percentage of AWCs that reported having a Medicine Kit"
                }
            ]
        )

    def test_chart_data_top_five(self):
        data = get_medicine_kit_data_chart(
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
                {'loc_name': 'st2', 'percent': 84.61538461538461},
                {'loc_name': 'st1', 'percent': 52.94117647058823},
                {'loc_name': 'st3', 'percent': 0.0},
                {'loc_name': 'st4', 'percent': 0.0},
                {'loc_name': 'st5', 'percent': 0.0},
            ]
        )

    def test_chart_data_bottom_five(self):
        data = get_medicine_kit_data_chart(
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
                {'loc_name': 'st3', 'percent': 0.0},
                {'loc_name': 'st4', 'percent': 0.0},
                {'loc_name': 'st5', 'percent': 0.0},
                {'loc_name': 'st6', 'percent': 0.0},
                {'loc_name': 'st7', 'percent': 0.0},
            ]
        )

    def test_chart_data_location_type(self):
        data = get_medicine_kit_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['location_type'], "State")

    def test_chart_data_all_locations(self):
        data = get_medicine_kit_data_chart(
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
                {'loc_name': 'st2', 'percent': 84.61538461538461},
                {'loc_name': 'st1', 'percent': 52.94117647058823},
                {'loc_name': 'st3', 'percent': 0.0},
                {'loc_name': 'st4', 'percent': 0.0},
                {'loc_name': 'st5', 'percent': 0.0},
                {'loc_name': 'st6', 'percent': 0.0},
                {'loc_name': 'st7', 'percent': 0.0},
            ]
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_medicine_kit_sector_data(
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
                "info": awcs_reported_medicine_kit_help_text(),
                "tooltips_data": {
                    "s2": {
                        "in_month": 2,
                        "all": 3
                    },
                    "s1": {
                        "in_month": 3,
                        "all": 5
                    }
                },
                "chart_data": [
                    {
                        "color": MapColors.BLUE,
                        "values": [
                            [
                                "s1",
                                0.6
                            ],
                            [
                                "s2",
                                0.6666666666666666
                            ]
                        ],
                        "strokeWidth": 2,
                        "classed": "dashed",
                        "key": ""
                    }
                ]
            }
        )
