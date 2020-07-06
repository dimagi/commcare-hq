from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.messages import wasting_help_text
from custom.icds_reports.reports.prevalence_of_severe import get_prevalence_of_severe_data_map, \
    get_prevalence_of_severe_data_chart, get_prevalence_of_severe_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestPrevalenceOfSevere(TestCase):
    maxDiff = None

    def test_map_data_keys(self):
        data = get_prevalence_of_severe_data_map(
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
        data = get_prevalence_of_severe_data_map(
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

    def test_map_data(self):
        data = get_prevalence_of_severe_data_map(
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
                'st1': {'moderate': 4,
                        'severe': 0,
                        'normal': 3,
                        'total_weighed': 317,
                        'total_measured': 7,
                        'total_height_eligible': 475,
                        'original_name': ['st1'],
                        'fillKey': '7%-100%'},
                'st2': {'moderate': 4,
                        'severe': 0,
                        'normal': 16,
                        'total_weighed': 378,
                        'total_measured': 24,
                        'total_height_eligible': 513,
                        'original_name': ['st2'],
                        'fillKey': '7%-100%'},
                'st7': {'moderate': 0,
                        'severe': 0,
                        'normal': 0,
                        'total_weighed': 0,
                        'total_measured': 0,
                        'total_height_eligible': 1,
                        'original_name': ['st7'],
                        'fillKey': '0%-5%'}
            }
        )

    def test_map_data_right_legend_info(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        expected = wasting_help_text("0 - 5 years")
        self.assertEqual(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(data['rightLegend']['average'], "25.81")

    def test_map_data_right_legend_extended_info(self):
        data = get_prevalence_of_severe_data_map(
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
                {'indicator': 'Total Children (0 - 5 years) weighed in given month:', 'value': '695'},
                {'indicator': 'Total Children (0 - 5 years) with weight and height measured in given month:',
                 'value': '31'},
                {'indicator': 'Number of children (0 - 5 years) unmeasured:', 'value': '294'},
                {'indicator': '% Severely Acute Malnutrition (0 - 5 years):', 'value': '0.00%'},
                {'indicator': '% Moderately Acute Malnutrition (0 - 5 years):', 'value': '25.81%'},
                {'indicator': '% Normal (0 - 5 years):', 'value': '61.29%'}
            ]
        )

    def test_map_data_fills(self):
        data = get_prevalence_of_severe_data_map(
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
                "0%-5%": MapColors.PINK,
                "5%-7%": MapColors.ORANGE,
                "7%-100%": MapColors.RED,
                "defaultFill": MapColors.GREY
            }
        )

    def test_map_data_slug(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(data['slug'], 'severe')

    def test_map_data_label(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(data['label'], 'Percent of Children Wasted (0 - 5 years)')

    def test_map_name_two_locations_represent_by_one_topojson(self):
        data = get_prevalence_of_severe_data_map(
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
                    'moderate': 4,
                    'total_measured': 7,
                    'normal': 3,
                    'original_name': ['b1', 'b2'],
                    'severe': 0,
                    'total_height_eligible': 475,
                    'total_weighed': 317,
                    'fillKey': '7%-100%'
                }
            }
        )

    def test_average_with_two_locations_represent_by_one_topojson(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
        )
        self.assertEqual(data['rightLegend']['average'], "57.14")

    def test_chart_data_keys_length(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(len(data), 5)

    def test_chart_data_location_type(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(data['location_type'], 'State')

    def test_chart_data_bottom_five(self):
        data = get_prevalence_of_severe_data_chart(
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
                {'loc_name': 'st7', 'percent': 0.0},
                {'loc_name': 'st2', 'percent': 16.666666666666668},
                {'loc_name': 'st1', 'percent': 57.142857142857146}
            ]
        )

    def test_chart_data_top_five(self):
        data = get_prevalence_of_severe_data_chart(
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
                {'loc_name': 'st7', 'percent': 0.0},
                {'loc_name': 'st2', 'percent': 16.666666666666668},
                {'loc_name': 'st1', 'percent': 57.142857142857146}
            ]
        )

    def test_chart_data_elements_length(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEqual(len(data['chart_data']), 3)

    def test_chart_data_pink(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertDictEqual(
            data['chart_data'][0],
            {
                "color": ChartColors.PINK,
                "classed": "dashed",
                "strokeWidth": 2,
                "values": [
                    {
                        "y": 0.0,
                        "x": 1485907200000,
                        "total_weighed": 0,
                        'total_measured': 0,
                        'total_height_eligible': 0
                    },
                    {
                        "y": 0.0,
                        "x": 1488326400000,
                        "total_weighed": 0,
                        'total_measured': 0,
                        'total_height_eligible': 0
                    },
                    {
                        "y": 0.5,
                        "x": 1491004800000,
                        "total_weighed": 690,
                        'total_measured': 12,
                        'total_height_eligible': 1021,
                    },
                    {
                        "y": 0.6129032258064516,
                        "x": 1493596800000,
                        "total_weighed": 695,
                        'total_measured': 31,
                        'total_height_eligible': 989,
                    }
                ],
                "key": "% normal"
            }
        )

    def test_chart_data_orange(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertDictEqual(
            data['chart_data'][1],
            {
                "color": ChartColors.ORANGE,
                "classed": "dashed",
                "strokeWidth": 2,
                "values": [
                    {
                        "y": 0.0,
                        "x": 1485907200000,
                        "total_weighed": 0,
                        'total_measured': 0,
                        'total_height_eligible': 0,
                    },
                    {
                        "y": 0.0,
                        "x": 1488326400000,
                        "total_weighed": 0,
                        'total_measured': 0,
                        'total_height_eligible': 0,
                    },
                    {
                        "y": 0.08333333333333333,
                        "x": 1491004800000,
                        "total_weighed": 690,
                        'total_measured': 12,
                        'total_height_eligible': 1021,
                    },
                    {
                        "y": 0.25806451612903225,
                        "x": 1493596800000,
                        "total_weighed": 695,
                        'total_measured': 31,
                        'total_height_eligible': 989,
                    }
                ],
                "key": "% moderately wasted (moderate acute malnutrition)"
            }
        )

    def test_chart_data_red(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertDictEqual(
            data['chart_data'][2],
            {
                "color": ChartColors.RED,
                "classed": "dashed",
                "strokeWidth": 2,
                "values": [
                    {
                        "y": 0.0,
                        "x": 1485907200000,
                        "total_weighed": 0,
                        'total_measured': 0,
                        'total_height_eligible': 0
                    },
                    {
                        "y": 0.0,
                        "x": 1488326400000,
                        "total_weighed": 0,
                        'total_measured': 0,
                        'total_height_eligible': 0
                    },
                    {
                        "y": 0.08333333333333333,
                        "x": 1491004800000,
                        "total_weighed": 690,
                        'total_measured': 12,
                        'total_height_eligible': 1021,
                    },
                    {
                        "y": 0.0,
                        "x": 1493596800000,
                        "total_weighed": 695,
                        'total_measured': 31,
                        'total_height_eligible': 989,
                    }
                ],
                "key": "% severely wasted (severe acute malnutrition)"
            }
        )

    def test_chart_data_all_locations(self):
        data = get_prevalence_of_severe_data_chart(
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
                {'loc_name': 'st7', 'percent': 0.0},
                {'loc_name': 'st2', 'percent': 16.666666666666668},
                {'loc_name': 'st1', 'percent': 57.142857142857146}
            ]
        )

    def test_sector_data_keys_length(self):
        data = get_prevalence_of_severe_sector_data(
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
        self.assertEqual(len(data), 3)

    def test_sector_data_info(self):
        data = get_prevalence_of_severe_sector_data(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'aggregation_level': 4
            },
            location_id='b1',
            loc_level='supervisor',
            show_test=False,
        )
        self.assertEqual(
            data['info'],
            wasting_help_text("0 - 5 years")
        )

    def test_sector_data_info_age_filter_0_years(self):
        data = get_prevalence_of_severe_sector_data(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'aggregation_level': 4,
                'age_tranche__in': ['0', '6']
            },
            location_id='b1',
            loc_level='supervisor',
            show_test=False,
        )
        self.assertEqual(
            data['info'],
            wasting_help_text("0-6 months (0-180 days)")
        )

    def test_sector_data_info_age_filter_1_year(self):
        data = get_prevalence_of_severe_sector_data(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'aggregation_level': 4,
                'age_tranche': '12'
            },
            location_id='b1',
            loc_level='supervisor',
            show_test=False,
        )
        self.assertEqual(
            data['info'],
            wasting_help_text("6-12 months (181-365 days)")
        )

    def test_sector_data_info_age_filter_5_years(self):
        data = get_prevalence_of_severe_sector_data(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'aggregation_level': 4,
                'age_tranche': '60'
            },
            location_id='b1',
            loc_level='supervisor',
            show_test=False,
        )
        self.assertEqual(
            data['info'],
            wasting_help_text("48-60 months (1461-1825 days)")
        )

    def test_sector_data_info_icds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_sector_data(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'aggregation_level': 4
            },
            location_id='b1',
            loc_level='supervisor',
            show_test=False,
        )
        self.assertEqual(
            data['info'],
            wasting_help_text("0 - 5 years")
        )

    def test_sector_data_info_icds_feature_flag_enabled_0_years(self):
        data = get_prevalence_of_severe_sector_data(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'aggregation_level': 4,
                'age_tranche__in': ['0', '6']
            },
            location_id='b1',
            loc_level='supervisor',
            show_test=False,
        )
        self.assertEqual(
            data['info'],
            wasting_help_text("0-6 months (0-180 days)")
        )

    def test_sector_data_info_icds_feature_flag_enabled_1_year(self):
        data = get_prevalence_of_severe_sector_data(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'aggregation_level': 4,
                'age_tranche': '12'
            },
            location_id='b1',
            loc_level='supervisor',
            show_test=False,
        )
        self.assertEqual(
            data['info'],
            wasting_help_text("6-12 months (181-365 days)")
        )

    def test_sector_data_info_icds_feature_flag_enabled_5_years(self):
        data = get_prevalence_of_severe_sector_data(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'block_id': 'b1',
                'aggregation_level': 4,
                'age_tranche': '60'
            },
            location_id='b1',
            loc_level='supervisor',
            show_test=False,
        )
        self.assertEqual(
            data['info'],
            wasting_help_text("48-60 months (1461-1825 days)")
        )

    def test_sector_data_tooltips_data(self):
        data = get_prevalence_of_severe_sector_data(
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
                    "total_weighed": 91,
                    "severe": 0,
                    "moderate": 3,
                    "total_measured": 4,
                    "normal": 1,
                    "total_height_eligible": 163,
                },
                "s1": {
                    "total_weighed": 67,
                    "severe": 0,
                    "moderate": 0,
                    "total_measured": 0,
                    "normal": 0,
                    "total_height_eligible": 72,
                }
            }
        )

    def test_sector_data_chart_data(self):
        data = get_prevalence_of_severe_sector_data(
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
                    "values": [["s1", 0.0], ["s2", 0.03296703296703297]],
                    "key": ""
                }
            ]
        )
