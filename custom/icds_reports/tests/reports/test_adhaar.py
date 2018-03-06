from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.adhaar import get_adhaar_data_map, get_adhaar_data_chart, get_adhaar_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestAdhaar(TestCase):
    maxDiff = None

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
                "st1": {
                    "in_month": 64,
                    "all": 221,
                    'original_name': ["st1"],
                    "fillKey": "25%-50%"
                },
                "st2": {
                    "in_month": 67,
                    "all": 279,
                    'original_name': ["st2"],
                    "fillKey": "0%-25%"
                }
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
        expected = (
            "Percentage of individuals registered using CAS "
            "whose Aadhaar identification has been captured"
        )
        self.assertEquals(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_adhaar_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['rightLegend']['average'], 26.486806467831137)

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
                    'value': "131"
                },
                {
                    'indicator': '% of ICDS beneficiaries whose Aadhaar has been captured:',
                    'value': '26.20%'
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
                    'in_month': 64,
                    'original_name': ['b1', 'b2'],
                    'all': 221,
                    'fillKey': '25%-50%'
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
        self.assertEquals(data['rightLegend']['average'], 30.264462809917354)

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
                    {
                        "loc_name": "st1",
                        "percent": 28.959276018099548
                    },
                    {
                        "loc_name": "st2",
                        "percent": 24.014336917562723
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 28.959276018099548
                    },
                    {
                        "loc_name": "st2",
                        "percent": 24.014336917562723
                    }
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
                                "y": 0.25,
                                "x": 1491004800000,
                                "all": 484
                            },
                            {
                                "y": 0.262,
                                "x": 1493596800000,
                                "all": 500
                            }
                        ],
                        "key": "Percentage of beneficiaries with Aadhaar numbers"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 28.959276018099548
                    },
                    {
                        "loc_name": "st2",
                        "percent": 24.014336917562723
                    }
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
                "info": "Percentage of individuals registered using "
                        "CAS whose Aadhaar identification has been captured",
                "tooltips_data": {
                    "s2": {
                        "in_month": 21,
                        "all": 66
                    },
                    "s1": {
                        "in_month": 23,
                        "all": 34
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
                                0.6764705882352942
                            ],
                            [
                                "s2",
                                0.3181818181818182
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
