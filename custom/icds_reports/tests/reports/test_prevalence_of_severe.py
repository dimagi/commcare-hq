from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
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
        self.assertEquals(len(data), 5)
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
        self.assertEquals(len(data), 3)
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
                "st1": {
                    "severe": 0,
                    "moderate": 0,
                    "normal": 0,
                    'total_height_eligible': 449,
                    "total_measured": 0,
                    "total_weighed": 302,
                    'original_name': ["st1"],
                    "fillKey": "0%-5%"
                },
                "st2": {
                    "severe": 0,
                    "moderate": 1,
                    "normal": 0,
                    'total_height_eligible': 490,
                    "total_measured": 0,
                    "total_weighed": 366,
                    'original_name': ["st2"],
                    "fillKey": "7%-100%"
                }
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
        expected = (
            "Of the children enrolled for Anganwadi services, whose weight and height was measured, the "
            "percentage of children between 0 - 5 years who were moderately/severely wasted in the "
            "current month. "
            "<br/><br/>"
            "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute undernutrition "
            "usually as a consequence of insufficient food intake or a high incidence of infectious diseases."
        )
        self.assertEquals(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['rightLegend']['average'], "0.15")

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
                {'indicator': 'Total Children (0 - 5 years) weighed in given month:', 'value': '668'},
                {'indicator': 'Total Children (0 - 5 years) with height measured in given month:',
                 'value': '0'},
                {'indicator': 'Number of children (0 - 5 years) unmeasured:', 'value': '271'},
                {'indicator': '% Severely Acute Malnutrition (0 - 5 years):', 'value': '0.00%'},
                {'indicator': '% Moderately Acute Malnutrition (0 - 5 years):', 'value': '100.00%'},
                {'indicator': '% Normal (0 - 5 years):', 'value': '0.00%'}
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
        self.assertEquals(data['slug'], 'severe')

    def test_map_data_label(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['label'], 'Percent of Children Wasted (0 - 5 years)')

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
                    'moderate': 0,
                    'total_measured': 0,
                    'normal': 0,
                    'original_name': ['b1', 'b2'],
                    'severe': 0,
                    'total_height_eligible': 449,
                    'total_weighed': 302,
                    'fillKey': '0%-5%'
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
        self.assertEquals(data['rightLegend']['average'], "0.00")

    def test_chart_data_keys_length(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(len(data), 5)

    def test_chart_data_location_type(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state'
        )
        self.assertEquals(data['location_type'], 'State')

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
                {
                    "loc_name": "st1",
                    "percent": 0.0
                },
                {
                    "loc_name": "st2",
                    "percent": 100.0
                },
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
                {
                    "loc_name": "st1",
                    "percent": 0.0
                },
                {
                    "loc_name": "st2",
                    "percent": 100.0
                },
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
        self.assertEquals(len(data['chart_data']), 3)

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
                        "y": 0.0,
                        "x": 1491004800000,
                        "total_weighed": 659,
                        'total_measured': 0,
                        'total_height_eligible': 964,
                    },
                    {
                        "y": 0.0,
                        "x": 1493596800000,
                        "total_weighed": 668,
                        'total_measured': 0,
                        'total_height_eligible': 939,
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
                        "y": 0.0,
                        "x": 1491004800000,
                        "total_weighed": 659,
                        'total_measured': 0,
                        'total_height_eligible': 964,
                    },
                    {
                        "y": 1.0,
                        "x": 1493596800000,
                        "total_weighed": 668,
                        'total_measured': 0,
                        'total_height_eligible': 939,
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
                        "y": 0.0,
                        "x": 1491004800000,
                        "total_weighed": 659,
                        'total_measured': 0,
                        'total_height_eligible': 964,
                    },
                    {
                        "y": 0.0,
                        "x": 1493596800000,
                        "total_weighed": 668,
                        'total_measured': 0,
                        'total_height_eligible': 939,
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
                {
                    "loc_name": "st1",
                    "percent": 0.0
                },
                {
                    "loc_name": "st2",
                    "percent": 100.0
                },
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
        self.assertEquals(len(data), 3)

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
            icds_feature_flag=False
        )
        self.assertEquals(
            data['info'],
            "Of the children enrolled for Anganwadi services, whose weight and height was measured, the "
            "percentage of children between 0 - 5 years enrolled who were moderately/severely wasted in the "
            "current month. "
            "<br/><br/>"
            "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute undernutrition "
            "usually as a consequence of insufficient food intake or a high incidence of infectious diseases."
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
            icds_feature_flag=False
        )
        self.assertEquals(
            data['info'],
            "Of the children enrolled for Anganwadi services, whose weight and height was measured, the "
            "percentage of children between 0-6 months (0-180 days) enrolled who were moderately/severely wasted "
            "in the current month. "
            "<br/><br/>"
            "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute undernutrition "
            "usually as a consequence of insufficient food intake or a high incidence of infectious diseases."
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
            icds_feature_flag=False
        )
        self.assertEquals(
            data['info'],
            "Of the children enrolled for Anganwadi services, whose weight and height was measured, the "
            "percentage of children between 6-12 months (181-365 days) enrolled who were moderately/severely "
            "wasted in the current month. "
            "<br/><br/>"
            "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute undernutrition "
            "usually as a consequence of insufficient food intake or a high incidence of infectious diseases."
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
            icds_feature_flag=False
        )
        self.assertEquals(
            data['info'],
            "Of the children enrolled for Anganwadi services, whose weight and height was measured, the "
            "percentage of children between 48-60 months (1461-1825 days) enrolled who were moderately/severely "
            "wasted in the current month. "
            "<br/><br/>"
            "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute undernutrition "
            "usually as a consequence of insufficient food intake or a high incidence of infectious diseases."
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
            icds_feature_flag=True
        )
        self.assertEquals(
            data['info'],
            "Of the children enrolled for Anganwadi services, whose weight and height was measured, the "
            "percentage of children between 0 - 5 years enrolled who were moderately/severely wasted in the "
            "current month. "
            "<br/><br/>"
            "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute undernutrition "
            "usually as a consequence of insufficient food intake or a high incidence of infectious diseases."
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
            icds_feature_flag=True
        )
        self.assertEquals(
            data['info'],
            "Of the children enrolled for Anganwadi services, whose weight and height was measured, the "
            "percentage of children between 0-6 months (0-180 days) enrolled who were moderately/severely wasted "
            "in the current month. "
            "<br/><br/>"
            "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute undernutrition "
            "usually as a consequence of insufficient food intake or a high incidence of infectious diseases."
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
            icds_feature_flag=True
        )
        self.assertEquals(
            data['info'],
            "Of the children enrolled for Anganwadi services, whose weight and height was measured, the "
            "percentage of children between 6-12 months (181-365 days) enrolled who were moderately/severely "
            "wasted in the current month. "
            "<br/><br/>"
            "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute undernutrition "
            "usually as a consequence of insufficient food intake or a high incidence of infectious diseases."
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
            icds_feature_flag=True
        )
        self.assertEquals(
            data['info'],
            "Of the children enrolled for Anganwadi services, whose weight and height was measured, the "
            "percentage of children between 48-60 months (1461-1825 days) enrolled who were moderately/severely "
            "wasted in the current month. "
            "<br/><br/>"
            "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute undernutrition "
            "usually as a consequence of insufficient food intake or a high incidence of infectious diseases."
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
                    "total_weighed": 84,
                    "severe": 0,
                    "moderate": 0,
                    "total_measured": 0,
                    "normal": 0,
                    "total_height_eligible": 150,
                },
                "s1": {
                    "total_weighed": 65,
                    "severe": 0,
                    "moderate": 0,
                    "total_measured": 0,
                    "normal": 0,
                    "total_height_eligible": 70,
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
                    "values": [
                        [
                            "s1",
                            0.0
                        ],
                        [
                            "s2",
                            0.0
                        ]
                    ],
                    "key": ""
                }
            ]
        )


@override_settings(SERVER_ENVIRONMENT='icds')
class TestPrevalenceOfSevereICDSFeatureFlag(TestCase):
    maxDiff = None

    def test_map_data_icds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state',
            show_test=False,
            icds_feature_flag=True
        )
        self.assertDictEqual(
            data['data'],
            {
                "st1": {
                    "severe": 0,
                    "moderate": 0,
                    "normal": 0,
                    'total_height_eligible': 454,
                    "total_measured": 0,
                    "total_weighed": 317,
                    'original_name': ["st1"],
                    "fillKey": "0%-5%"
                },
                "st2": {
                    "severe": 0,
                    "moderate": 1,
                    "normal": 0,
                    'total_height_eligible': 497,
                    "total_measured": 0,
                    "total_weighed": 379,
                    'original_name': ["st2"],
                    "fillKey": "7%-100%"
                }
            }
        )

    def test_map_data_right_legend_info_icds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state',
            show_test=False,
            icds_feature_flag=True
        )
        expected = (
            "Of the children enrolled for Anganwadi services, whose weight and height was measured, the "
            "percentage of children between 0 - 5 years who were moderately/severely wasted in the current month. "
            "<br/><br/>"
            "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute undernutrition "
            "usually as a consequence of insufficient food intake or a high incidence of infectious diseases."
        )
        self.assertEquals(data['rightLegend']['info'], expected)

    def test_map_data_right_legend_average_icds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state',
            show_test=False,
            icds_feature_flag=True
        )
        self.assertEquals(data['rightLegend']['average'], "0.14")

    def test_map_data_right_legend_extended_info_icds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state',
            show_test=False,
            icds_feature_flag=True
        )
        self.assertListEqual(
            data['rightLegend']['extended_info'],
            [
                {'indicator': 'Total Children (0 - 5 years) weighed in given month:', 'value': '696'},
                {'indicator': 'Total Children (0 - 5 years) with height measured in given month:',
                 'value': '0'},
                {'indicator': 'Number of children (0 - 5 years) unmeasured:', 'value': '255'},
                {'indicator': '% Severely Acute Malnutrition (0 - 5 years):', 'value': '0.00%'},
                {'indicator': '% Moderately Acute Malnutrition (0 - 5 years):', 'value': '100.00%'},
                {'indicator': '% Normal (0 - 5 years):', 'value': '0.00%'}
            ]
        )

    def test_map_data_label_icds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state',
            show_test=False,
            icds_feature_flag=True
        )
        self.assertEquals(data['label'], 'Percent of Children Wasted (0 - 5 years)')

    def test_map_name_two_locations_represent_by_one_topojson_icds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
            show_test=False,
            icds_feature_flag=True
        )
        self.assertDictEqual(
            data['data'],
            {
                'block_map': {
                    'moderate': 0,
                    'total_measured': 0,
                    'normal': 0,
                    'original_name': ['b1', 'b2'],
                    'severe': 0,
                    'total_height_eligible': 454,
                    'total_weighed': 317,
                    'fillKey': '0%-5%'
                }
            }
        )

    def test_average_with_two_locations_represent_by_one_topojson_icds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_data_map(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'state_id': 'st1',
                'district_id': 'd1',
                'aggregation_level': 3
            },
            loc_level='block',
            show_test=False,
            icds_feature_flag=True
        )
        self.assertEquals(data['rightLegend']['average'], "0.00")

    def test_chart_data_bottom_fiveicds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state',
            show_test=False,
            icds_feature_flag=True
        )
        self.assertListEqual(
            data['bottom_five'],
            [
                {
                    "loc_name": "st1",
                    "percent": 0.0
                },
                {
                    "loc_name": "st2",
                    "percent": 100.0,
                },
            ]
        )

    def test_chart_data_top_five_icds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state',
            show_test=False,
            icds_feature_flag=True
        )
        self.assertListEqual(
            data['top_five'],
            [
                {
                    "loc_name": "st1",
                    "percent": 0.0
                },
                {
                    "loc_name": "st2",
                    "percent": 100.0,
                },
            ]
        )

    def test_chart_data_pink_icds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state',
            show_test=False,
            icds_feature_flag=True
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
                        "y": 0.0,
                        "x": 1491004800000,
                        "total_weighed": 691,
                        'total_measured': 1,
                        'total_height_eligible': 981,
                    },
                    {
                        "y": 0.0,
                        "x": 1493596800000,
                        "total_weighed": 696,
                        'total_measured': 0,
                        'total_height_eligible': 951,
                    }
                ],
                "key": "% normal"
            }
        )

    def test_chart_data_orange_icds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state',
            show_test=False,
            icds_feature_flag=True
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
                        "y": 0.00,
                        "x": 1491004800000,
                        "total_weighed": 691,
                        'total_measured': 1,
                        'total_height_eligible': 981,
                    },
                    {
                        "y": 1.0,
                        "x": 1493596800000,
                        "total_weighed": 696,
                        'total_measured': 00,
                        'total_height_eligible': 951,
                    }
                ],
                "key": "% moderately wasted (moderate acute malnutrition)"
            }
        )

    def test_chart_data_red_icds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state',
            show_test=False,
            icds_feature_flag=True
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
                        "y": 1.0,
                        "x": 1491004800000,
                        "total_weighed": 691,
                        'total_measured': 1,
                        'total_height_eligible': 981,
                    },
                    {
                        "y": 0.0,
                        "x": 1493596800000,
                        "total_weighed": 696,
                        'total_measured': 0,
                        'total_height_eligible': 951,
                    }
                ],
                "key": "% severely wasted (severe acute malnutrition)"
            }
        )

    def test_chart_data_all_locations_icds_feature_flag_enabled(self):
        data = get_prevalence_of_severe_data_chart(
            'icds-cas',
            config={
                'month': (2017, 5, 1),
                'aggregation_level': 1
            },
            loc_level='state',
            show_test=False,
            icds_feature_flag=True
        )
        self.assertListEqual(
            data['all_locations'],
            [
                {
                    "loc_name": "st1",
                    "percent": 0.0
                },
                {
                    "loc_name": "st2",
                    "percent": 100.0,
                },
            ]
        )

    def test_sector_data_tooltips_data_icds_feature_flag_enabled(self):
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
            icds_feature_flag=True
        )
        self.assertDictEqual(
            data['tooltips_data'],
            {
                "s1": {
                    "total_weighed": 67,
                    "severe": 0,
                    "moderate": 0,
                    "total_measured": 0,
                    "normal": 0,
                    "total_height_eligible": 71,
                },
                "s2": {
                    "total_weighed": 91,
                    "severe": 0,
                    "moderate": 0,
                    "total_measured": 0,
                    "normal": 0,
                    "total_height_eligible": 153,
                },
            }
        )

    def test_sector_data_chart_data_icds_feature_flag_enabled(self):
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
            icds_feature_flag=True
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
                            0.0
                        ],
                        [
                            "s2",
                            0.0
                        ]
                    ],
                    "key": ""
                }
            ]
        )
