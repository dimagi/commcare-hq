from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.children_initiated_data import get_children_initiated_data_map, \
    get_children_initiated_data_chart, get_children_initiated_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestChildrenInitiated(TestCase):
    maxDiff = None

    def test_map_data_keys(self):
        data = get_children_initiated_data_map(
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
        data = get_children_initiated_data_map(
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
        data = get_children_initiated_data_map(
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
                    "all": 17,
                    "children": 14,
                    'original_name': ["st1"],
                    "fillKey": "60%-100%"
                },
                "st2": {
                    "all": 23,
                    "children": 20,
                    'original_name': ["st2"],
                    "fillKey": "60%-100%"
                }
            }
        )

    def test_map_data_right_legend_info(self):
        data = get_children_initiated_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        expected = (
            "Percentage of children between 6 - 8 months"
            " given timely introduction to solid, semi-solid or soft food."
        )
        self.assertEquals(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_children_initiated_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['rightLegend']['average'], 84.65473145780052)

    def test_map_data_right_legend_extended_info(self):
        data = get_children_initiated_data_map(
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
                {'indicator': 'Total number of children between age 6 - 8 months:', 'value': "40"},
                {
                    'indicator': (
                        'Total number of children (6-8 months) given timely introduction '
                        'to sold or semi-solid food in the given month:'
                    ),
                    'value': "34"
                },
                {
                    'indicator': (
                        '% children (6-8 months) given timely introduction '
                        'to solid or semi-solid food in the given month:'
                    ),
                    'value': '85.00%'
                }
            ]
        )

    def test_map_data_fills(self):
        data = get_children_initiated_data_map(
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
        data = get_children_initiated_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['slug'], 'severe')

    def test_map_data_label(self):
        data = get_children_initiated_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['label'], 'Percent Children (6-8 months) initiated Complementary Feeding')

    def test_map_name_two_locations_represent_by_one_topojson(self):
        data = get_children_initiated_data_map(
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
                    'all': 17,
                    'original_name': ['b1', 'b2'],
                    'children': 14,
                    'fillKey': '60%-100%'
                }
            }
        )

    def test_average_with_two_locations_represent_by_one_topojson(self):
        data = get_children_initiated_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
        )
        self.assertEquals(data['rightLegend']['average'], 80.71428571428572)

    def test_chart_data(self):
        self.assertDictEqual(
            get_children_initiated_data_chart(
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
                    {
                        "loc_name": "st2",
                        "percent": 86.95652173913044
                    },
                    {
                        "loc_name": "st1",
                        "percent": 82.3529411764706
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "percent": 86.95652173913044
                    },
                    {
                        "loc_name": "st1",
                        "percent": 82.3529411764706
                    }
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
                                "y": 0.34375,
                                "x": 1491004800000,
                                "all": 32,
                                "in_month": 11
                            },
                            {
                                "y": 0.85,
                                "x": 1493596800000,
                                "all": 40,
                                "in_month": 34
                            }
                        ],
                        "key": "% Children began complementary feeding"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st2",
                        "percent": 86.95652173913044
                    },
                    {
                        "loc_name": "st1",
                        "percent": 82.3529411764706
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_children_initiated_sector_data(
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
                "info": "Percentage of children between 6 - 8 months "
                        "given timely introduction to solid, semi-solid or soft food.",
                "tooltips_data": {
                    "s2": {
                        "all": 7,
                        "children": 6
                    },
                    "s1": {
                        "all": 3,
                        "children": 3
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
                                1.0
                            ],
                            [
                                "s2",
                                0.8571428571428571
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
