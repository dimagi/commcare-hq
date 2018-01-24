from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.new_born_with_low_weight import get_newborn_with_low_birth_weight_map, \
    get_newborn_with_low_birth_weight_chart, get_newborn_with_low_birth_weight_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestNewBornWithLowWeight(TestCase):
    maxDiff = None

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
                "st1": {
                    "in_month": 4,
                    "low_birth": 2,
                    'original_name': ["st1"],
                    "fillKey": "20%-60%"
                },
                "st2": {
                    "in_month": 3,
                    "low_birth": 0,
                    'original_name': ["st2"],
                    "fillKey": "0%-20%"
                }
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
            "Percentage of newborns with born with birth weight less than 2500 grams."
            "<br/><br/>Newborns with Low Birth Weight are closely associated with foetal "
            "and neonatal mortality and morbidity, inhibited growth and cognitive development,"
            " and chronic diseases later in life"
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
        self.assertEquals(data['rightLegend']['average'], 25.0)

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
                {'indicator': 'Total Number of Newborns born in given month:', 'value': "7"},
                {'indicator': 'Number of Newborns with LBW in given month:', 'value': "2"},
                {'indicator': '% newborns with LBW in given month:', 'value': '28.57%'},
                {'indicator': '% Unweighed:', 'value': '71.43%'}
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
                    'in_month': 4,
                    'original_name': ['b1', 'b2'],
                    'low_birth': 2,
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
        self.assertEquals(data['rightLegend']['average'], 66.66666666666667)

    def test_chart_data(self):
        self.assertDictEqual(
            get_newborn_with_low_birth_weight_chart(
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
                        "percent": 0.0
                    },
                    {
                        "loc_name": "st1",
                        "percent": 100.0
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "percent": 0.0
                    },
                    {
                        "loc_name": "st1",
                        "percent": 100.0
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
                                "low_birth": 0
                            },
                            {
                                "y": 0,
                                "x": 1488326400000,
                                "all": 0,
                                "low_birth": 0
                            },
                            {
                                "y": 0.0,
                                "x": 1491004800000,
                                "all": 3,
                                "low_birth": 0
                            },
                            {
                                "y": 0.6666666666666666,
                                "x": 1493596800000,
                                "all": 3,
                                "low_birth": 2
                            }
                        ],
                        "key": "% Newborns with Low Birth Weight"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st2",
                        "percent": 0.0
                    },
                    {
                        "loc_name": "st1",
                        "percent": 100.0
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_newborn_with_low_birth_weight_data(
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
                "info": "Percentage of newborns with born with birth weight less than 2500 grams."
                        "<br/><br/>Newborns with Low Birth Weight are closely associated with foetal"
                        " and neonatal mortality and morbidity, inhibited growth and cognitive development,"
                        " and chronic diseases later in life",
                "tooltips_data": {
                    "s2": {
                        "in_month": 0,
                        "low_birth": 0
                    },
                    "s1": {
                        "in_month": 1,
                        "low_birth": 1
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
                                0.0
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
