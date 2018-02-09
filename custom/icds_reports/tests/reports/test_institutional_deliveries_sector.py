from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.institutional_deliveries_sector import get_institutional_deliveries_data_map, \
    get_institutional_deliveries_data_chart, get_institutional_deliveries_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestInstitutionalDeliveriesSector(TestCase):
    maxDiff = None

    def test_map_data_keys(self):
        data = get_institutional_deliveries_data_map(
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
        data = get_institutional_deliveries_data_map(
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
        data = get_institutional_deliveries_data_map(
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
                    "all": 13,
                    "children": 9,
                    'original_name': ["st1"],
                    "fillKey": "60%-100%"
                },
                "st2": {
                    "all": 13,
                    "children": 11,
                    'original_name': ["st2"],
                    "fillKey": "60%-100%"
                }
            }
        )

    def test_map_data_right_legend_info(self):
        data = get_institutional_deliveries_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        expected = (
            "Percentage of pregnant women who delivered in a public or "
            "private medical facility in the last month. <br/><br/>Delivery in medical"
            " instituitions is associated with a decrease in maternal mortality rate"
        )
        self.assertEquals(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_institutional_deliveries_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['rightLegend']['average'], 76.92307692307692)

    def test_map_data_right_legend_extended_info(self):
        data = get_institutional_deliveries_data_map(
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
                    'indicator': 'Total number of pregnant women who delivered in the last month:',
                    'value': "26"
                },
                {
                    'indicator': (
                        'Total number of pregnant women who delivered in a public/private '
                        'medical facilitiy in the last month:'
                    ),
                    'value': "20"
                },
                {
                    'indicator': (
                        '% pregnant women who delivered in a '
                        'public or private medical facility in the last month:'
                    ),
                    'value': '76.92%'
                }
            ]
        )

    def test_map_data_fills(self):
        data = get_institutional_deliveries_data_map(
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
        data = get_institutional_deliveries_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['slug'], 'institutional_deliveries')

    def test_map_data_label(self):
        data = get_institutional_deliveries_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['label'], 'Percent Instituitional Deliveries')

    def test_map_name_two_locations_represent_by_one_topojson(self):
        data = get_institutional_deliveries_data_map(
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
                    'all': 13,
                    'original_name': ['b1', 'b2'],
                    'children': 9,
                    'fillKey': '60%-100%'
                }
            }
        )

    def test_average_with_two_locations_represent_by_one_topojson(self):
        data = get_institutional_deliveries_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
        )
        self.assertEquals(data['rightLegend']['average'], 61.36363636363637)

    def test_chart_data(self):
        self.assertDictEqual(
            get_institutional_deliveries_data_chart(
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
                        "percent": 84.61538461538461
                    },
                    {
                        "loc_name": "st1",
                        "percent": 69.23076923076923
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "percent": 84.61538461538461
                    },
                    {
                        "loc_name": "st1",
                        "percent": 69.23076923076923
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
                                "y": 0.3,
                                "x": 1491004800000,
                                "all": 20,
                                "in_month": 6
                            },
                            {
                                "y": 0.7692307692307693,
                                "x": 1493596800000,
                                "all": 26,
                                "in_month": 20
                            }
                        ],
                        "key": "% Institutional deliveries"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st2",
                        "percent": 84.61538461538461
                    },
                    {
                        "loc_name": "st1",
                        "percent": 69.23076923076923
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_institutional_deliveries_sector_data(
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
                "info": "Percentage of pregnant women who delivered in a public or private medical "
                        "facility in the last month. <br/><br/>Delivery in medical instituitions"
                        " is associated with a decrease in maternal mortality rate",
                "tooltips_data": {
                    "s2": {
                        "all": 0,
                        "children": 0
                    },
                    "s1": {
                        "all": 2,
                        "children": 1
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
                                0.5
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
