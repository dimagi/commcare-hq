from __future__ import absolute_import

from django.test.utils import override_settings

from custom.icds_reports.reports.infants_weight_scale import get_infants_weight_scale_data_map, \
    get_infants_weight_scale_data_chart, get_infants_weight_scale_sector_data
from django.test import TestCase
from custom.icds_reports.const import ChartColors, MapColors


@override_settings(SERVER_ENVIRONMENT='icds')
class TestInfantsWeightScale(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_infants_weight_scale_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": "Percentage of AWCs that reported having a weighing scale for infants",
                    "average": 80.54298642533936,
                    'extended_info': [
                        {'indicator': 'Total number of AWCs with a weighing scale for infants:', 'value': "24"},
                        {'indicator': '% of AWCs with a weighing scale for infants:', 'value': '80.00%'}
                    ]
                },
                "label": "Percentage of AWCs that reported having a weighing scale for infants",
                "data": {
                    "st1": {
                        "in_month": 13,
                        "original_name": ["st1"],
                        "all": 17,
                        "fillKey": "75%-100%"
                    },
                    "st2": {
                        "in_month": 11,
                        "original_name": ["st2"],
                        "all": 13,
                        "fillKey": "75%-100%"
                    }
                },
                "slug": "infants_weight_scale",
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
            get_infants_weight_scale_data_map(
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
                    "info": "Percentage of AWCs that reported having a weighing scale for infants",
                    "average": 77.08333333333334,
                    'extended_info': [
                        {'indicator': 'Total number of AWCs with a weighing scale for infants:', 'value': "13"},
                        {'indicator': '% of AWCs with a weighing scale for infants:', 'value': '76.47%'}
                    ]
                },
                "label": "Percentage of AWCs that reported having a weighing scale for infants",
                "data": {
                    "block_map": {
                        "in_month": 13,
                        "original_name": [
                            "b1",
                            "b2"
                        ],
                        "all": 17,
                        "fillKey": "75%-100%"
                    }
                },
                "slug": "infants_weight_scale",
                "fills": {
                    "0%-25%": MapColors.RED,
                    "25%-75%": MapColors.ORANGE,
                    "75%-100%": MapColors.PINK,
                    "defaultFill": MapColors.GREY
                }
            }
        )

    def test_chart_data(self):
        data = get_infants_weight_scale_data_chart(
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
                            "y": 0.7142857142857143,
                            "x": 1491004800000,
                            "in_month": 10
                        },
                        {
                            "y": 0.8,
                            "x": 1493596800000,
                            "in_month": 24
                        }
                    ],
                    "key": "Percentage of AWCs that reported having a weighing scale for infants"
                }
            ]
        )

    def test_chart_data_keys(self):
        data = get_infants_weight_scale_data_chart(
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

    def test_chart_data_top_five_locations(self):
        data = get_infants_weight_scale_data_chart(
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
                    "percent": 84.61538461538461
                },
                {
                    "loc_name": "st1",
                    "percent": 76.47058823529412
                }
            ]
        )

    def test_chart_data_bottom_five_locations(self):
        data = get_infants_weight_scale_data_chart(
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
                    "percent": 84.61538461538461
                },
                {
                    "loc_name": "st1",
                    "percent": 76.47058823529412
                }
            ]
        )

    def test_chart_data_location_type(self):
        data = get_infants_weight_scale_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['location_type'], "State")

    def test_chart_data_all_locations(self):
        data = get_infants_weight_scale_data_chart(
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
                    "percent": 84.61538461538461
                },
                {
                    "loc_name": "st1",
                    "percent": 76.47058823529412
                }
            ]
        )

    def test_sector_data_keys(self):
        data = get_infants_weight_scale_sector_data(
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
        self.assertIn('info', data)
        self.assertIn('tooltips_data', data)
        self.assertIn('chart_data', data)

    def test_sector_data(self):
        data = get_infants_weight_scale_sector_data(
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
                            0.8
                        ],
                        [
                            "s2",
                            1.0
                        ]
                    ],
                    "key": ""
                }
            ]
        )

    def test_sector_data_info(self):
        data = get_infants_weight_scale_sector_data(
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
            "Percentage of AWCs that reported having a weighing scale for infants"
        )

    def test_sector_data_tooltips_data(self):
        data = get_infants_weight_scale_sector_data(
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
                    "in_month": 3,
                    "all": 3
                },
                "s1": {
                    "in_month": 4,
                    "all": 5
                }
            }
        )
