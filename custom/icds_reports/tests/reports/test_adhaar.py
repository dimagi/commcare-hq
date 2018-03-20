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
                    "in_month": 190,
                    "all": 761,
                    'original_name': ["st1"],
                    "fillKey": "0%-25%"
                },
                "st2": {
                    "in_month": 151,
                    "all": 821,
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
        self.assertEqual(data['rightLegend']['average'], 21.679676558666156)

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
                    'value': "341"
                },
                {
                    'indicator': '% of ICDS beneficiaries whose Aadhaar has been captured:',
                    'value': '21.55%'
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
                    'in_month': 190,
                    'original_name': ['b1', 'b2'],
                    'all': 761,
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
        self.assertEqual(data['rightLegend']['average'], 24.82689277717887)

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
                        "percent": 24.967148488830485
                    },
                    {
                        "loc_name": "st2",
                        "percent": 18.392204628501826
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 24.967148488830485
                    },
                    {
                        "loc_name": "st2",
                        "percent": 18.392204628501826
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
                                "y": 0.19520319786808793,
                                "x": 1491004800000,
                                "all": 1501
                            },
                            {
                                "y": 0.21554993678887485,
                                "x": 1493596800000,
                                "all": 1582
                            }
                        ],
                        "key": "Percentage of beneficiaries with Aadhaar numbers"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 24.967148488830485
                    },
                    {
                        "loc_name": "st2",
                        "percent": 18.392204628501827
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
                        "in_month": 50,
                        "all": 255
                    },
                    "s1": {
                        "in_month": 71,
                        "all": 134
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
                                0.5298507462686567
                            ],
                            [
                                "s2",
                                0.19607843137254902
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
