
from __future__ import absolute_import

from django.test.utils import override_settings

from django.test import TestCase

from custom.icds_reports.reports.functional_toilet import get_functional_toilet_data_map, \
    get_functional_toilet_data_chart, get_functional_toilet_sector_data
from custom.icds_reports.const import ChartColors, MapColors


@override_settings(SERVER_ENVIRONMENT='icds')
class TestFunctionalToilet(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_functional_toilet_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": "Percentage of AWCs that reported having a functional toilet",
                    "average": 50.452488687782804,
                    'extended_info': [
                        {'indicator': 'Total number of AWCs with a functional toilet:', 'value': "15"},
                        {'indicator': '% of AWCs with a functional toilet:', 'value': '50.00%'}
                    ]
                },
                "label": "Percentage of AWCs that reported having a functional toilet",
                "data": {
                    "st1": {
                        "in_month": 8,
                        "original_name": ["st1"],
                        "all": 17,
                        "fillKey": "25%-75%"
                    },
                    "st2": {
                        "in_month": 7,
                        "original_name": ["st2"],
                        "all": 13,
                        "fillKey": "25%-75%"
                    }
                },
                "slug": "functional_toilet",
                "fills": {
                    "0%-25%": MapColors.RED,
                    "25%-75%": MapColors.ORANGE,
                    "75%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                }
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_functional_toilet_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'aggregation_level': 3
                },
                loc_level='block',
            ),
            {
                "rightLegend": {
                    "info": "Percentage of AWCs that reported having a functional toilet",
                    "average": 47.05882352941177,
                    'extended_info': [
                        {'indicator': 'Total number of AWCs with a functional toilet:', 'value': "8"},
                        {'indicator': '% of AWCs with a functional toilet:', 'value': '47.06%'}
                    ]
                },
                "label": "Percentage of AWCs that reported having a functional toilet",
                "data": {
                    "block_map": {
                        "in_month": 8,
                        "original_name": [
                            "b1",
                            "b2"
                        ],
                        "all": 17,
                        "fillKey": "25%-75%"
                    }
                },
                "slug": "functional_toilet",
                "fills": {
                    "0%-25%": MapColors.RED,
                    "25%-75%": MapColors.ORANGE,
                    "75%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                }
            }
        )

    def test_chart_data(self):
        data = get_functional_toilet_data_chart(
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
                            "y": 0.5714285714285714,
                            "x": 1491004800000,
                            "in_month": 8
                        },
                        {
                            "y": 0.5,
                            "x": 1493596800000,
                            "in_month": 15
                        }
                    ],
                    "strokeWidth": 2,
                    "classed": "dashed",
                    "key": "Percentage of AWCs that reported having a functional toilet"
                }
            ]
        )

    def test_chart_data_keys(self):
        data = get_functional_toilet_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(len(data.keys()), 5)
        self.assertIn('top_five', data)
        self.assertIn('bottom_five', data)
        self.assertIn('all_locations', data)
        self.assertIn('chart_data', data)
        self.assertIn('location_type', data)

    def test_chart_data_top_five(self):
        data = get_functional_toilet_data_chart(
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
                    "percent": 53.84615384615385
                },
                {
                    "loc_name": "st1",
                    "percent": 47.05882352941177
                }
            ]
        )

    def test_chart_data_bottom_five(self):
        data = get_functional_toilet_data_chart(
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
                    "percent": 53.84615384615385
                },
                {
                    "loc_name": "st1",
                    "percent": 47.05882352941177
                }
            ]
        )

    def test_chart_data_location_type(self):
        data = get_functional_toilet_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['location_type'], "State")

    def test_chart_data_all_locations(self):
        data = get_functional_toilet_data_chart(
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
                    "percent": 53.84615384615385
                },
                {
                    "loc_name": "st1",
                    "percent": 47.05882352941177
                }
            ]
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_functional_toilet_sector_data(
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
                "info": "Percentage of AWCs that reported having a functional toilet",
                "tooltips_data": {
                    "s2": {
                        "in_month": 0,
                        "all": 3
                    },
                    "s1": {
                        "in_month": 4,
                        "all": 5
                    }
                },
                "chart_data": [
                    {
                        "color": MapColors.BLUE,
                        "values": [
                            [
                                "s1",
                                0.8
                            ],
                            [
                                "s2",
                                0.0
                            ]
                        ],
                        "strokeWidth": 2,
                        "classed": "dashed",
                        "key": ""
                    }
                ]
            }
        )
