from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.immunization_coverage_data import get_immunization_coverage_data_map, \
    get_immunization_coverage_data_chart, get_immunization_coverage_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds-new')
class TestImmunizationCoverage(TestCase):
    maxDiff = None

    def test_map_data_keys(self):
        data = get_immunization_coverage_data_map(
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
        data = get_immunization_coverage_data_map(
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
        data = get_immunization_coverage_data_map(
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
                    "all": 573,
                    "children": 85,
                    'original_name': ["st1"],
                    "fillKey": "0%-20%"
                },
                "st2": {
                    "all": 620,
                    "children": 45,
                    'original_name': ["st2"],
                    "fillKey": "0%-20%"
                }
            }
        )

    def test_map_data_right_legend_info(self):
        data = get_immunization_coverage_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        expected = (
            "Percentage of children 1 year+ who have received complete immunization as per "
            "National Immunization Schedule of India required by age 1."
            "<br/><br/>"
            "This includes the following immunizations:<br/>"
            "If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/>"
            "If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1"
        )
        self.assertEquals(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_immunization_coverage_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['rightLegend']['average'], 11.046135224905703)

    def test_map_data_right_legend_extended_info(self):
        data = get_immunization_coverage_data_map(
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
                    'indicator': 'Total number of ICDS Child beneficiaries older than 1 year:',
                    'value': "1,193"
                },
                {
                    'indicator': (
                        'Total number of children who have recieved '
                        'complete immunizations required by age 1:'
                    ),
                    'value': "130"
                },
                {
                    'indicator': (
                        '% of children who have recieved complete immunizations required by age 1:'
                    ),
                    'value': '10.90%'
                }
            ]
        )

    def test_map_data_fills(self):
        data = get_immunization_coverage_data_map(
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
        data = get_immunization_coverage_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['slug'], 'institutional_deliveries')

    def test_map_data_label(self):
        data = get_immunization_coverage_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['label'], 'Percent Immunization Coverage at 1 year')

    def test_map_name_two_locations_represent_by_one_topojson(self):
        data = get_immunization_coverage_data_map(
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
                    'all': 573,
                    'original_name': ['b1', 'b2'],
                    'children': 85,
                    'fillKey': '0%-20%'
                }
            }
        )

    def test_average_with_two_locations_represent_by_one_topojson(self):
        data = get_immunization_coverage_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
        )
        self.assertEquals(data['rightLegend']['average'], 14.909190638712824)

    def test_chart_data(self):
        self.assertDictEqual(
            get_immunization_coverage_data_chart(
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
                        "percent": 14.834205933682373
                    },
                    {
                        "loc_name": "st2",
                        "percent": 7.258064516129032
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 14.834205933682373
                    },
                    {
                        "loc_name": "st2",
                        "percent": 7.258064516129032
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
                                "y": 0.10765349032800672,
                                "x": 1491004800000,
                                "all": 1189,
                                "in_month": 128
                            },
                            {
                                "y": 0.10896898575020955,
                                "x": 1493596800000,
                                "all": 1193,
                                "in_month": 130
                            }
                        ],
                        "key": "% Children received complete immunizations by 1 year"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 14.834205933682373
                    },
                    {
                        "loc_name": "st2",
                        "percent": 7.258064516129032
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_immunization_coverage_sector_data(
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
                "info": "Percentage of children 1 year+ who have received complete immunization as per "
                        "National Immunization Schedule of India required by age 1."
                        "<br/><br/>"
                        "This includes the following immunizations:<br/>"
                        "If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/>"
                        "If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1",
                "tooltips_data": {
                    "s2": {
                        "all": 193,
                        "children": 3
                    },
                    "s1": {
                        "all": 100,
                        "children": 31
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
                                0.31
                            ],
                            [
                                "s2",
                                0.015544041450777202
                            ]
                        ],
                        "key": ""
                    }
                ]
            }

        )
