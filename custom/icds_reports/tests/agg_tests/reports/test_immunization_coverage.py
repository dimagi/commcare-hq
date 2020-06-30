from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.reports.immunization_coverage_data import get_immunization_coverage_data_map, \
    get_immunization_coverage_data_chart, get_immunization_coverage_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestImmunizationCoverage(TestCase):

    def test_map_data_keys(self):
        data = get_immunization_coverage_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(len(data), 5)
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
        self.assertEqual(len(data), 3)
        self.assertIn('info', data)
        self.assertIn('average', data)
        self.assertIn('extended_info', data)

    def test_map_data_with_age_1_2_ff(self):
        data = get_immunization_coverage_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state',
        )
        self.assertDictEqual(
            data['data'],
            {
                'st1': {'all': 44, 'original_name': ['st1'], 'children': 4, 'fillKey': '0%-20%'},
                'st2': {'all': 57, 'original_name': ['st2'], 'children': 6, 'fillKey': '0%-20%'}
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
            "Of the total number of children enrolled for Anganwadi Services who are between 1-2 years old,"
            " the percentage of children who have received the complete immunization as per the National"
            " Immunization Schedule of India that is required by age 1.<br/><br/>This includes the following"
            " immunizations:<br/>If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/>If"
            " DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1"
        )
        self.assertEqual(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_immunization_coverage_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(data['rightLegend']['average'], 9.900990099009901)

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
                    'indicator': 'Total number of ICDS Child beneficiaries between 1-2 years old:',
                    'value': "101"
                },
                {
                    'indicator': (
                        'Total number of children between 1-2 years old who have received '
                        'complete immunizations required by age 1:'
                    ),
                    'value': "10"
                },
                {
                    'indicator': (
                        '% of children between 1-2 years old who have received complete immunizations'
                        ' required by age 1:'
                    ),
                    'value': '9.90%'
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
        self.assertEqual(data['slug'], 'institutional_deliveries')

    def test_map_data_label(self):
        data = get_immunization_coverage_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(data['label'], 'Percent Immunization Coverage at 1 year')

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
                    'all': 44,
                    'original_name': ['b1', 'b2'],
                    'children': 4,
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
        self.assertEqual(data['rightLegend']['average'], 9.090909090909092)

    def test_chart_data_with_age_1_2(self):
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
                'chart_data': [
                    {
                        'values': [
                            {
                                'x': 1485907200000,
                                'y': 0,
                                'all': 0,
                                'in_month': 0
                            },
                            {
                                'x': 1488326400000,
                                'y': 0,
                                'all': 0,
                                'in_month': 0
                            },
                            {
                                'x': 1491004800000,
                                'y': 0.0784313725490196,
                                'all': 102,
                                'in_month': 8
                            },
                            {
                                'x': 1493596800000,
                                'y': 0.09900990099009901,
                                'all': 101,
                                'in_month': 10
                            }
                        ],
                        'key': '% Children between 1-2 years old who received complete immunizations by 1 year',
                        'strokeWidth': 2,
                        'classed': 'dashed',
                        'color': '#005ebd'
                    }
                ],
                'all_locations': [
                    {'loc_name': 'st2', 'percent': 10.526315789473685},
                    {'loc_name': 'st1', 'percent': 9.090909090909092}
                ],
                'top_five': [
                    {'loc_name': 'st2', 'percent': 10.526315789473685},
                    {'loc_name': 'st1', 'percent': 9.090909090909092}
                ],
                'bottom_five': [
                    {'loc_name': 'st2', 'percent': 10.526315789473685},
                    {'loc_name': 'st1', 'percent': 9.090909090909092}
                ],
                'location_type': 'State'
            }
        )

    def test_sector_data_with_age_1_2(self):
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
                "info": "Of the total number of children enrolled for Anganwadi Services who are between"
                        " 1-2 years old, "
                        "the percentage of children who have received the complete immunization as per the "
                        "National Immunization Schedule of India that is required by age 1."
                        "<br/><br/>"
                        "This includes the following immunizations:<br/>"
                        "If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/>"
                        "If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1",
                "tooltips_data": {
                    "s2": {
                        "all": 12,
                        "children": 3
                    },
                    "s1": {
                        "all": 1,
                        "children": 0
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
                                0.0
                            ],
                            [
                                "s2",
                                0.25
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
