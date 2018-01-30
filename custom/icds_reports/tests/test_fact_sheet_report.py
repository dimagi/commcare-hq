from __future__ import absolute_import

from datetime import datetime
from django.test.testcases import TestCase
from custom.icds_reports.views import FactSheetsReport
from custom.icds_reports.utils import get_location_level


class TestFactSheetReportMaternalAndChildNutrition(TestCase):
    def get_data(self):
        config = {
            'aggregation_level': 1,
            'month': datetime(2017, 6, 1).date(),
            'previous_month': datetime(2017, 5, 1).date(),
            'two_before': datetime(2017, 4, 1).date(),
            'category': 'maternal_and_child_nutrition',
            'domain': 'icds-cas'
        }

        loc_level = get_location_level(config.get('aggregation_level'))
        return FactSheetsReport(config=config, loc_level=loc_level).get_data()

    def test_section_amount(self):
        self.assertEqual(len(self.get_data()['config']['sections']), 1)

    def test_nutrition_status_of_children_amount_of_config_rows(self):
        self.assertEqual(len(self.get_data()['config']['sections'][0]['rows_config']), 12)

    def test_status_weighed(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][0],
            {
                'average': {
                    'html': 68.97066136250622,
                    'sort_key': 68.97066136250622
                },
                'data': [
                    {'html': 'Weighing Efficiency (Children <5 weighed)'},
                    {'html': 67.61252446183953, 'sort_key': 67.61252446183953},
                    {'html': 70.37411526794742, 'sort_key': 70.37411526794742},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Weighing Efficiency (Children <5 weighed)',
                'slug': 'status_weighed'
            }
        )

    def test_nutrition_status_unweighed(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][1],
            {
                'data': [
                    {'html': 'Total number of unweighed children (0-5 Years)'},
                    {'html': 331, 'sort_key': 331},
                    {'html': 293, 'sort_key': 293},
                    {'html': 0}],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'header': 'Total number of unweighed children (0-5 Years)',
                'reverseColors': True,
                'slug': 'nutrition_status_unweighed'
            }
        )

    def test_severely_underweight(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][2],
            {
                'average': {
                    'html': 2.523431867339582,
                    'sort_key': 2.523431867339582
                },
                'data': [
                    {'html': 'Children from 0 - 5 years who are severely underweight (weight-for-age)'},
                    {'html': 2.170767004341534, 'sort_key': 2.170767004341534},
                    {'html': 2.8735632183908044, 'sort_key': 2.8735632183908044},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children from 0 - 5 years who are severely underweight (weight-for-age)',
                'reverseColors': True,
                'slug': 'severely_underweight'
            }
        )

    def test_moderately_underweight(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][3],
            {
                'average': {
                    'html': 20.90843547224225,
                    'sort_key': 20.90843547224225
                },
                'data': [
                    {'html': 'Children from 0-5 years who are moderately underweight (weight-for-age)'},
                    {'html': 23.154848046309695, 'sort_key': 23.154848046309695},
                    {'html': 18.67816091954023, 'sort_key': 18.67816091954023},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children from 0-5 years who are moderately underweight (weight-for-age)',
                'reverseColors': True,
                'slug': 'moderately_underweight'
            }
        )

    def test_status_normal(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][4],
            {
                'average': {
                    'html': 76.56813266041817,
                    'sort_key': 76.56813266041817
                },
                'data': [
                    {'html': 'Children from 0-5 years who are at normal weight-for-age'},
                    {'html': 74.67438494934876, 'sort_key': 74.67438494934876},
                    {'html': 78.44827586206897, 'sort_key': 78.44827586206897},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children from 0-5 years who are at normal weight-for-age',
                'slug': 'status_normal'
            }
        )

    def test_wasting_severe(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][5],
            {
                'average': {
                    'html': 0.05254860746190226,
                    'sort_key': 0.05254860746190226
                },
                'data': [
                    {'html': 'Children from 6 - 60 months with severe acute malnutrition (weight-for-height)'},
                    {'html': 0.1037344398340249, 'sort_key': 0.1037344398340249},
                    {'html': 0.0, 'sort_key': 0.0},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children from 6 - 60 months with severe acute malnutrition (weight-for-height)',
                'reverseColors': True,
                'slug': 'wasting_severe'
            }
        )

    def test_wasting_moderate(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][6],
            {
                'average': {
                    'html': 0.4729374671571203,
                    'sort_key': 0.4729374671571203
                },
                'data': [
                    {'html': 'Children from 6 - 60 months with moderate acute malnutrition (weight-for-height)'},
                    {'html': 0.1037344398340249, 'sort_key': 0.1037344398340249},
                    {'html': 0.8519701810436635, 'sort_key': 0.8519701810436635},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children from 6 - 60 months with moderate acute malnutrition (weight-for-height)',
                'reverseColors': True,
                'slug': 'wasting_moderate'
            }
        )

    def test_wasting_normal(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][7],
            {
                'average': {
                    'html': 1.3137151865475565,
                    'sort_key': 1.3137151865475565
                },
                'data': [
                    {'html': 'Children from 6 - 60 months with normal weight-for-height'},
                    {'html': 0.6224066390041494, 'sort_key': 0.6224066390041494},
                    {'html': 2.0234291799787005, 'sort_key': 2.0234291799787005},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children from 6 - 60 months with normal weight-for-height',
                'slug': 'wasting_normal'
            }
        )

    def test_stunting_severe(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][8],
            {
                'average': {
                    'html': 0.8407777193904361,
                    'sort_key': 0.8407777193904361
                },
                'data': [
                    {'html': 'Children from 6 - 60 months with severe stunting (height-for-age)'},
                    {'html': 0.5186721991701245, 'sort_key': 0.5186721991701245},
                    {'html': 1.1714589989350372, 'sort_key': 1.1714589989350372},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children from 6 - 60 months with severe stunting (height-for-age)',
                'reverseColors': True,
                'slug': 'stunting_severe'
            }
        )

    def test_stunting_moderate(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][9],
            {
                'average': {
                    'html': 0.6305832895428272,
                    'sort_key': 0.6305832895428272
                },
                'data': [
                    {'html': 'Children from 6 - 60 months with moderate stunting (height-for-age)'},
                    {'html': 0.4149377593360996, 'sort_key': 0.4149377593360996},
                    {'html': 0.8519701810436635, 'sort_key': 0.8519701810436635},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children from 6 - 60 months with moderate stunting (height-for-age)',
                'reverseColors': True,
                'slug': 'stunting_moderate'
            }
        )

    def test_stunting_normal(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][10],
            {
                'average': {
                    'html': 0.7882291119285338,
                    'sort_key': 0.7882291119285338
                },
                'data': [
                    {'html': 'Children from 6 - 60 months with normal height-for-age'},
                    {'html': 0.2074688796680498, 'sort_key': 0.2074688796680498},
                    {'html': 1.384451544195953, 'sort_key': 1.384451544195953},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children from 6 - 60 months with normal height-for-age',
                'slug': 'stunting_normal'
            }
        )

    def test_low_birth_weight(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][11],
            {
                'average': {
                    'html': 50.0,
                    'sort_key': 50.0
                },
                'data': [
                    {'html': 'Percent of children born in month with low birth weight'},
                    {'html': 0.0, 'sort_key': 0.0},
                    {'html': 50.0, 'sort_key': 50.0},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Percent of children born in month with low birth weight',
                'slug': 'low_birth_weight'
            }
        )

    def test_rest_of_data(self):
        data = self.get_data()
        del(data['config']['sections'][0]['rows_config'])
        self.assertDictEqual(
            data,
            {
                'config': {
                    'category': 'maternal_and_child_nutrition',
                    'sections': [
                        {
                            'months': ['Apr 2017', 'May 2017', 'Jun 2017'],
                            'order': 1,
                            'section_title': 'Nutrition Status of Children',
                            'slug': 'nutrition_status_of_children'
                        }
                    ],
                    'title': 'Maternal and Child Nutrition'
                }
            }
        )


class TestFactSheetReportInterventions(TestCase):
    def get_data(self):
        config = {
            'aggregation_level': 1,
            'month': datetime(2017, 6, 1).date(),
            'previous_month': datetime(2017, 5, 1).date(),
            'two_before': datetime(2017, 4, 1).date(),
            'category': 'interventions',
            'domain': 'icds-cas'
        }

        loc_level = get_location_level(config.get('aggregation_level'))
        return FactSheetsReport(config=config, loc_level=loc_level).get_data()

    def test_section_amount(self):
        self.assertEqual(len(self.get_data()['config']['sections']), 3)

    def test_nutrition_status_of_children_amount_of_config_rows(self):
        self.assertEqual(len(self.get_data()['config']['sections'][0]['rows_config']), 1)

    def test_nutrition_status_of_children(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0],
            {
                'months': ['Apr 2017', 'May 2017', 'Jun 2017'],
                'order': 1,
                'rows_config': [
                    {
                        'average': {
                            'html': 10.896898575020955,
                            'sort_key': 10.896898575020955
                        },
                        'data': [
                            {'html': 'Children 1 year+ who have recieved complete immunization'
                                     ' required by age 1.'},
                            {'html': 10.765349032800673, 'sort_key': 10.765349032800673},
                            {'html': 10.896898575020955, 'sort_key': 10.896898575020955},
                            {'html': 0}
                        ],
                        'data_source': 'AggChildHealthMonthlyDataSource',
                        'format': 'percent',
                        'header': 'Children 1 year+ who have recieved complete immunization required by age 1.',
                        'slug': 'fully_immunized'
                    }
                ],
                'section_title': 'Nutrition Status of Children',
                'slug': 'nutrition_status_of_children'
            }
        )

    def test_nutrition_status_of_pregnant_women_amount_of_config_rows(self):
        self.assertEqual(len(self.get_data()['config']['sections'][1]['rows_config']), 6)

    def test_severe_anemic(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][1]['rows_config'][0],
            {
                'average': {
                    'html': 25.806451612903224,
                    'sort_key': 25.806451612903224
                },
                'data': [
                    {'html': 'Pregnant women who are anemic'},
                    {'html': 17.307692307692307, 'sort_key': 17.307692307692307},
                    {'html': 25.806451612903224, 'sort_key': 25.806451612903224},
                    {'html': 0}
                ],
                'data_source': 'AggCCSRecordMonthlyDataSource',
                'format': 'percent',
                'header': 'Pregnant women who are anemic',
                'reverseColors': True,
                'slug': 'severe_anemic'
            }
        )

    def test_tetanus_complete(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][1]['rows_config'][1],
            {
                'average': {
                    'html': 0.0,
                    'sort_key': 0.0
                },
                'data': [
                    {'html': 'Pregnant women with tetanus completed'},
                    {'html': 0.0, 'sort_key': 0.0},
                    {'html': 0.0, 'sort_key': 0.0},
                    {'html': 0}
                ],
                'data_source': 'AggCCSRecordMonthlyDataSource',
                'format': 'percent',
                'header': 'Pregnant women with tetanus completed',
                'slug': 'tetanus_complete'
            }
        )

    def test_anc_1(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][1]['rows_config'][2],
            {
                'average': {
                    'html': 0.0,
                    'sort_key': 0.0
                },
                'data': [
                    {'html': 'Pregnant women who had at least 1 ANC visit by delivery'},
                    {'html': 0.0, 'sort_key': 0.0},
                    {'html': 0.0, 'sort_key': 0.0},
                    {'html': 0}
                ],
                'data_source': 'AggCCSRecordMonthlyDataSource',
                'format': 'percent',
                'header': 'Pregnant women who had at least 1 ANC visit by delivery',
                'slug': 'anc_1'
            }
        )

    def test_anc_2(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][1]['rows_config'][3],
            {
                'average': {
                    'html': 0.0,
                    'sort_key': 0.0
                },
                'data': [
                    {'html': 'Pregnant women who had at least 2 ANC visits by delivery'},
                    {'html': 0.0, 'sort_key': 0.0},
                    {'html': 0.0, 'sort_key': 0.0},
                    {'html': 0}
                ],
                'data_source': 'AggCCSRecordMonthlyDataSource',
                'format': 'percent',
                'header': 'Pregnant women who had at least 2 ANC visits by delivery',
                'slug': 'anc_2'
            }
        )

    def test_anc_3(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][1]['rows_config'][4],
            {
                'average': {
                    'html': 0.0,
                    'sort_key': 0.0
                },
                'data': [
                    {'html': 'Pregnant women who had at least 3 ANC visits by delivery'},
                    {'html': 0.0, 'sort_key': 0.0},
                    {'html': 0.0, 'sort_key': 0.0},
                    {'html': 0}
                ],
                'data_source': 'AggCCSRecordMonthlyDataSource',
                'format': 'percent',
                'header': 'Pregnant women who had at least 3 ANC visits by delivery',
                'slug': 'anc_3'
            }
        )

    def test_anc_4(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][1]['rows_config'][5],
            {
                'average': {
                    'html': 0.0,
                    'sort_key': 0.0
                },
                'data': [
                    {'html': 'Pregnant women who had at least 4 ANC visits by delivery'},
                    {'html': 0.0, 'sort_key': 0.0},
                    {'html': 0.0, 'sort_key': 0.0},
                    {'html': 0}
                ],
                'data_source': 'AggCCSRecordMonthlyDataSource',
                'format': 'percent',
                'header': 'Pregnant women who had at least 4 ANC visits by delivery',
                'slug': 'anc_4'
            }
        )

    def test_awc_infrastructure_amount_of_config_rows(self):
        self.assertEqual(len(self.get_data()['config']['sections'][2]['rows_config']), 3)

    def test_medicine_kits(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][2]['rows_config'][0],
            {
                'average': {
                    'html': 66.66666666666667,
                    'sort_key': 66.66666666666667
                },
                'data': [
                    {'html': 'AWCs reported medicine kit'},
                    {'html': 78.57142857142857, 'sort_key': 78.57142857142857},
                    {'html': 66.66666666666667, 'sort_key': 66.66666666666667},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'format': 'percent',
                'header': 'AWCs reported medicine kit',
                'slug': 'medicine_kits'
            }
        )

    def test_baby_weighing_scale(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][2]['rows_config'][1],
            {
                'average': {
                    'html': 80.0,
                    'sort_key': 80.0
                },
                'data': [
                    {'html': 'AWCs reported weighing scale for infants'},
                    {'html': 71.42857142857143, 'sort_key': 71.42857142857143},
                    {'html': 80.0, 'sort_key': 80.0},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'format': 'percent',
                'header': 'AWCs reported weighing scale for infants',
                'slug': 'baby_weighing_scale'
            }
        )

    def test_adult_weighing_scale(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][2]['rows_config'][2],
            {
                'average': {
                    'html': 30.0,
                    'sort_key': 30.0
                },
                'data': [
                    {'html': 'AWCs reported weighing scale for mother and child'},
                    {'html': 21.428571428571427, 'sort_key': 21.428571428571427},
                    {'html': 30.0, 'sort_key': 30.0},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'format': 'percent',
                'header': 'AWCs reported weighing scale for mother and child',
                'slug': 'adult_weighing_scale'
            }
        )

    def test_rest_of_data(self):
        data = self.get_data()
        del (data['config']['sections'][0]['rows_config'])
        del (data['config']['sections'][1]['rows_config'])
        del (data['config']['sections'][2]['rows_config'])
        self.assertDictEqual(
            data,
            {
                'config': {
                    'category': 'interventions',
                    'sections': [
                        {
                            'months': ['Apr 2017', 'May 2017', 'Jun 2017'],
                            'order': 1,
                            'section_title': 'Nutrition Status of Children',
                            'slug': 'nutrition_status_of_children'
                        },
                        {
                            'months': ['Apr 2017', 'May 2017', 'Jun 2017'],
                            'order': 3,
                            'section_title': 'Nutrition Status of Pregnant Women',
                            'slug': 'nutrition_status_of_pregnant_women'},
                        {
                            'months': ['Apr 2017', 'May 2017', 'Jun 2017'],
                            'order': 5,
                            'section_title': 'AWC Infrastructure',
                            'slug': 'awc_infrastructure'
                        }
                    ],
                    'title': 'Interventions'
                }
            }
        )


class TestFactSheetReportBehaviorChange(TestCase):
    def get_data(self):
        config = {
            'aggregation_level': 1,
            'month': datetime(2017, 6, 1).date(),
            'previous_month': datetime(2017, 5, 1).date(),
            'two_before': datetime(2017, 4, 1).date(),
            'category': 'behavior_change',
            'domain': 'icds-cas'
        }

        loc_level = get_location_level(config.get('aggregation_level'))
        return FactSheetsReport(config=config, loc_level=loc_level).get_data()

    def test_section_amount(self):
        self.assertEqual(len(self.get_data()['config']['sections']), 2)

    def test_child_feeding_indicators_amount_of_config_rows(self):
        self.assertEqual(len(self.get_data()['config']['sections'][0]['rows_config']), 7)

    def test_breastfed_at_birth(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][0],
            {
                'average': {
                    'html': 57.142857142857146,
                    'sort_key': 57.142857142857146
                },
                'data': [
                    {'html': 'Percentage of children who were put to the breast within one hour of birth.'},
                    {'html': 25.0, 'sort_key': 25.0},
                    {'html': 57.142857142857146, 'sort_key': 57.142857142857146},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Percentage of children who were put to the breast within one hour of birth.',
                'slug': 'breastfed_at_birth'
            }
        )

    def test_exclusively_breastfed(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][1],
            {
                'average': {
                    'html': 56.0,
                    'sort_key': 56.0
                },
                'data': [
                    {'html': 'Infants 0-6 months of age who are fed exclusively with breast milk.'},
                    {'html': 22.413793103448278, 'sort_key': 22.413793103448278},
                    {'html': 56.0, 'sort_key': 56.0},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Infants 0-6 months of age who are fed exclusively with breast milk.',
                'slug': 'exclusively_breastfed'
            }
        )

    def test_cf_initiation(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][2],
            {
                'average': {
                    'html': 85.0,
                    'sort_key': 85.0
                },
                'data': [
                    {'html': 'Children between 6 - 8 months given timely '
                             'introduction to solid, semi-solid or soft food.'},
                    {'html': 34.375, 'sort_key': 34.375},
                    {'html': 85.0, 'sort_key': 85.0},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children between 6 - 8 months given timely introduction to solid, '
                          'semi-solid or soft food.',
                'slug': 'cf_initiation'
            }
        )

    def test_complementary_feeding(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][3],
            {
                'average': {
                    'html': 72.5609756097561,
                    'sort_key': 72.5609756097561
                },
                'data': [
                    {'html': 'Children from 6 - 24 months complementary feeding'},
                    {'html': 31.288343558282207, 'sort_key': 31.288343558282207},
                    {'html': 72.5609756097561, 'sort_key': 72.5609756097561},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children from 6 - 24 months complementary feeding',
                'slug': 'complementary_feeding'
            }
        )

    def test_diet_diversity(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][4],
            {
                'average': {
                    'html': 57.926829268292686,
                    'sort_key': 57.926829268292686
                },
                'data': [
                    {'html': 'Children from 6 - 24 months consuming at least 4 food groups'},
                    {'html': 25.153374233128833, 'sort_key': 25.153374233128833},
                    {'html': 57.926829268292686, 'sort_key': 57.926829268292686},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children from 6 - 24 months consuming at least 4 food groups',
                'slug': 'diet_diversity'
            }
        )

    def test_diet_quantity(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][5],
            {
                'average': {
                    'html': 47.5609756097561,
                    'sort_key': 47.5609756097561
                },
                'data': [
                    {'html': 'Children from 6 - 24 months consuming adequate food'},
                    {'html': 24.539877300613497, 'sort_key': 24.539877300613497},
                    {'html': 47.5609756097561, 'sort_key': 47.5609756097561},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children from 6 - 24 months consuming adequate food',
                'slug': 'diet_quantity'
            }
        )

    def test_handwashing(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][6],
            {
                'average': {
                    'html': 68.29268292682927,
                    'sort_key': 68.29268292682927
                },
                'data': [
                    {'html': 'Children from 6 - 24 months whose mothers handwash before feeding'},
                    {'html': 26.993865030674847, 'sort_key': 26.993865030674847},
                    {'html': 68.29268292682927, 'sort_key': 68.29268292682927},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'format': 'percent',
                'header': 'Children from 6 - 24 months whose mothers handwash before feeding',
                'slug': 'handwashing'
            }
        )

    def test_nutrition_status_of_pregnant_women_amount_of_config_rows(self):
        self.assertEqual(len(self.get_data()['config']['sections'][1]['rows_config']), 3)

    def test_resting(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][1]['rows_config'][0],
            {
                'average': {
                    'html': 105.16129032258064,
                    'sort_key': 105.16129032258064
                },
                'data': [
                    {'html': 'Women resting during pregnancy'},
                    {'html': 62.5, 'sort_key': 62.5},
                    {'html': 105.16129032258064, 'sort_key': 105.16129032258064},
                    {'html': 0}
                ],
                'data_source': 'AggCCSRecordMonthlyDataSource',
                'format': 'percent',
                'header': 'Women resting during pregnancy',
                'slug': 'resting'
            }
        )

    def test_extra_meal(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][1]['rows_config'][1],
            {
                'average': {
                    'html': 105.16129032258064,
                    'sort_key': 105.16129032258064
                },
                'data': [
                    {'html': 'Women eating an extra meal during pregnancy'},
                    {'html': 62.5, 'sort_key': 62.5},
                    {'html': 105.16129032258064, 'sort_key': 105.16129032258064},
                    {'html': 0}
                ],
                'data_source': 'AggCCSRecordMonthlyDataSource',
                'format': 'percent',
                'header': 'Women eating an extra meal during pregnancy',
                'slug': 'extra_meal'
            }
        )

    def test_trimester(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][1]['rows_config'][2],
            {
                'average': {
                    'html': 72.15189873417721,
                    'sort_key': 72.15189873417721
                },
                'data': [
                    {'html': 'Pregnant women in 3rd trimester counselled on immediate and '
                             'exclusive breastfeeding during home visit'},
                    {'html': 39.62264150943396, 'sort_key': 39.62264150943396},
                    {'html': 72.15189873417721, 'sort_key': 72.15189873417721},
                    {'html': 0}
                ],
                'data_source': 'AggCCSRecordMonthlyDataSource',
                'format': 'percent',
                'header': 'Pregnant women in 3rd trimester counselled on immediate and '
                          'exclusive breastfeeding during home visit',
                'slug': 'trimester'
            }
        )

    def test_rest_of_data(self):
        data = self.get_data()
        del (data['config']['sections'][0]['rows_config'])
        del (data['config']['sections'][1]['rows_config'])
        self.assertDictEqual(
            data,
            {
                'config': {
                    'category': 'behavior_change',
                    'sections': [
                        {
                            'months': ['Apr 2017', 'May 2017', 'Jun 2017'],
                            'order': 2,
                            'section_title': 'Child Feeding Indicators',
                            'slug': 'child_feeding_indicators'
                        },
                        {
                            'months': ['Apr 2017', 'May 2017', 'Jun 2017'],
                            'order': 3,
                            'section_title': 'Nutrition Status of Pregnant Women',
                            'slug': 'nutrition_status_of_pregnant_women'
                        }
                    ],
                    'title': 'Behavior Change'
                }
            }
        )


class TestFactSheetReportWaterSanitationAndHygiene(TestCase):
    def get_data(self):
        config = {
            'aggregation_level': 1,
            'month': datetime(2017, 6, 1).date(),
            'previous_month': datetime(2017, 5, 1).date(),
            'two_before': datetime(2017, 4, 1).date(),
            'category': 'water_sanitation_and_hygiene',
            'domain': 'icds-cas'
        }

        loc_level = get_location_level(config.get('aggregation_level'))
        return FactSheetsReport(config=config, loc_level=loc_level).get_data()

    def test_section_amount(self):
        self.assertEqual(len(self.get_data()['config']['sections']), 1)

    def test_awc_infrastructure_amount_of_config_rows(self):
        self.assertEqual(len(self.get_data()['config']['sections'][0]['rows_config']), 2)

    def test_clean_water(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][0],
            {
                'average': {
                    'html': 96.66666666666667,
                    'sort_key': 96.66666666666667
                },
                'data': [
                    {'html': 'AWCs reported clean drinking water'},
                    {'html': 100.0, 'sort_key': 100.0},
                    {'html': 96.66666666666667, 'sort_key': 96.66666666666667},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'format': 'percent',
                'header': 'AWCs reported clean drinking water',
                'slug': 'clean_water'
            }
        )

    def test_functional_toilet(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][1],
            {
                'average': {
                    'html': 50.0,
                    'sort_key': 50.0
                },
                'data': [
                    {'html': 'AWCs reported functional toilet'},
                    {'html': 57.142857142857146, 'sort_key': 57.142857142857146},
                    {'html': 50.0, 'sort_key': 50.0},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'format': 'percent',
                'header': 'AWCs reported functional toilet',
                'slug': 'functional_toilet'
            }
        )

    def test_rest_of_data(self):
        data = self.get_data()
        del (data['config']['sections'][0]['rows_config'])
        self.assertDictEqual(
            data,
            {
                'config': {
                    'category': 'water_sanitation_and_hygiene',
                    'sections': [
                        {
                            'months': ['Apr 2017', 'May 2017', 'Jun 2017'],
                            'order': 5,
                            'section_title': 'AWC Infrastructure',
                            'slug': 'awc_infrastructure'
                        }
                    ],
                    'title': 'Water Sanitation And Hygiene'
                }
            }
        )


class TestFactSheetReportDemographics(TestCase):
    def get_data(self):
        config = {
            'aggregation_level': 1,
            'month': datetime(2017, 6, 1).date(),
            'previous_month': datetime(2017, 5, 1).date(),
            'two_before': datetime(2017, 4, 1).date(),
            'category': 'demographics',
            'domain': 'icds-cas'
        }

        loc_level = get_location_level(config.get('aggregation_level'))
        return FactSheetsReport(config=config, loc_level=loc_level).get_data()

    def test_section_amount(self):
        self.assertEqual(len(self.get_data()['config']['sections']), 1)

    def test_demographics_amount_of_config_rows(self):
        self.assertEqual(len(self.get_data()['config']['sections'][0]['rows_config']), 19)

    def test_cases_household(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][0],
            {
                'average': {
                    'html': 6964,
                    'sort_key': 6964
                },
                'data': [
                    {'html': 'Number of Households'},
                    {'html': 6964, 'sort_key': 6964},
                    {'html': 6964, 'sort_key': 6964},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'header': 'Number of Households',
                'slug': 'cases_household',
            }
        )

    def test_cases_person_all(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][1],
            {
                'average': {
                    'html': 962,
                    'sort_key': 962
                },
                'data': [
                    {'html': 'Total Number of Household Members'},
                    {'html': 954, 'sort_key': 954},
                    {'html': 962, 'sort_key': 962},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'header': 'Total Number of Household Members',
                'slug': 'cases_person_all',
            }
        )

    def test_cases_person_beneficiary(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][2],
            {
                'average': {
                    'html': 500,
                    'sort_key': 500
                },
                'data': [
                    {'html': 'Total number of members enrolled at AWC'},
                    {'html': 484, 'sort_key': 484},
                    {'html': 500, 'sort_key': 500},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'header': 'Total number of members enrolled at AWC',
                'slug': 'cases_person_beneficiary',
            }
        )

    def test_aadhar(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][3],
            {
                'average': {
                    'html': 26.2,
                    'sort_key': 26.2
                },
                'data': [
                    {'html': 'Percent Aadhaar-seeded beneficiaries'},
                    {'html': 25.0, 'sort_key': 25.0},
                    {'html': 26.2, 'sort_key': 26.2},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'format': 'percent',
                'header': 'Percent Aadhaar-seeded beneficiaries',
                'slug': 'aadhar',
            }
        )

    def test_cases_ccs_pregnant_all(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][4],
            {
                'average': {
                    'html': 155,
                    'sort_key': 155
                },
                'data': [
                    {'html': 'Total pregnant women '},
                    {'html': 104, 'sort_key': 104},
                    {'html': 155, 'sort_key': 155},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'header': 'Total pregnant women ',
                'slug': 'cases_ccs_pregnant_all',
            }
        )

    def test_cases_ccs_pregnant(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][5],
            {
                'average': {
                    'html': 155,
                    'sort_key': 155
                },
                'data': [
                    {'html': 'Total pregnant women enrolled for services at AWC'},
                    {'html': 104, 'sort_key': 104},
                    {'html': 155, 'sort_key': 155},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'header': 'Total pregnant women enrolled for services at AWC',
                'slug': 'cases_ccs_pregnant',
            }
        )

    def test_cases_ccs_lactating_all(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][6],
            {
                'average': {
                    'html': 166,
                    'sort_key': 166
                },
                'data': [
                    {'html': 'Total lactating women'},
                    {'html': 159, 'sort_key': 159},
                    {'html': 166, 'sort_key': 166},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'header': 'Total lactating women',
                'slug': 'cases_ccs_lactating_all',
            }
        )

    def test_cases_ccs_lactating(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][7],
            {
                'average': {
                    'html': 166,
                    'sort_key': 166
                },
                'data': [
                    {'html': 'Total lactating women registered for services at AWC'},
                    {'html': 159, 'sort_key': 159},
                    {'html': 166, 'sort_key': 166},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'header': 'Total lactating women registered for services at AWC',
                'slug': 'cases_ccs_lactating',
            }
        )

    def test_cases_child_health_all(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][8],
            {
                'average': {
                    'html': 1287,
                    'sort_key': 1287
                },
                'data': [
                    {'html': 'Total children (0-6 years)'},
                    {'html': 1262, 'sort_key': 1262},
                    {'html': 1287, 'sort_key': 1287},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'header': 'Total children (0-6 years)',
                'slug': 'cases_child_health_all',
            }
        )

    def test_cases_child_health(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][9],
            {
                'average': {
                    'html': 1287,
                    'sort_key': 1287
                },
                'data': [
                    {'html': 'Total chldren (0-6 years) enrolled for ICDS services'},
                    {'html': 1262, 'sort_key': 1262},
                    {'html': 1287, 'sort_key': 1287},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'header': 'Total chldren (0-6 years) enrolled for ICDS services',
                'slug': 'cases_child_health',
            }
        )

    def test_zero(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][10],
            {
                'average': {
                    'html': 10,
                    'sort_key': 10
                },
                'data': [
                    {'html': 'Children (0-28 days)  enrolled for ICDS services'},
                    {'html': 5, 'sort_key': 5},
                    {'html': 5, 'sort_key': 5},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'header': 'Children (0-28 days)  enrolled for ICDS services',
                'slug': 'zero',
            }
        )

    def test_one(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][11],
            {
                'average': {
                    'html': 98,
                    'sort_key': 98
                },
                'data': [
                    {'html': 'Children (28 days - 6 months)  enrolled for ICDS services'},
                    {'html': 53, 'sort_key': 53},
                    {'html': 45, 'sort_key': 45},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'header': 'Children (28 days - 6 months)  enrolled for ICDS services',
                'slug': 'one',
            }
        )

    def test_two(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][12],
            {
                'average': {
                    'html': 95,
                    'sort_key': 95
                },
                'data': [
                    {'html': 'Children (6 months - 1 year)  enrolled for ICDS services'},
                    {'html': 44, 'sort_key': 44},
                    {'html': 51, 'sort_key': 51},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'header': 'Children (6 months - 1 year)  enrolled for ICDS services',
                'slug': 'two',
            }
        )

    def test_three(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][13],
            {
                'average': {
                    'html': 450,
                    'sort_key': 450
                },
                'data': [
                    {'html': 'Children (1 year - 3 years)  enrolled for ICDS services'},
                    {'html': 237, 'sort_key': 237},
                    {'html': 213, 'sort_key': 213},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'header': 'Children (1 year - 3 years)  enrolled for ICDS services',
                'slug': 'three',
            }
        )

    def test_four(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][14],
            {
                'average': {
                    'html': 1896,
                    'sort_key': 1896
                },
                'data': [
                    {'html': 'Children (3 years - 6 years)  enrolled for ICDS services'},
                    {'html': 923, 'sort_key': 923},
                    {'html': 973, 'sort_key': 973},
                    {'html': 0}
                ],
                'data_source': 'AggChildHealthMonthlyDataSource',
                'header': 'Children (3 years - 6 years)  enrolled for ICDS services',
                'slug': 'four',
            }
        )

    def test_cases_person_adolescent_girls_11_14_all(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][15],
            {
                'average': {
                    'html': 34,
                    'sort_key': 34
                },
                'data': [
                    {'html': 'Adolescent girls (11-14 years)'},
                    {'html': 38, 'sort_key': 38},
                    {'html': 34, 'sort_key': 34},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'header': 'Adolescent girls (11-14 years)',
                'slug': 'cases_person_adolescent_girls_11_14_all',
            }
        )

    def test_cases_person_adolescent_girls_15_18_all(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][16],
            {
                'average': {
                    'html': 13,
                    'sort_key': 13
                },
                'data': [
                    {'html': 'Adolescent girls (15-18 years)'},
                    {'html': 19, 'sort_key': 19},
                    {'html': 13, 'sort_key': 13},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'header': 'Adolescent girls (15-18 years)',
                'slug': 'cases_person_adolescent_girls_15_18_all',
            }
        )

    def test_cases_person_adolescent_girls_11_14(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][17],
            {
                'average': {
                    'html': 34,
                    'sort_key': 34
                },
                'data': [
                    {'html': 'Adolescent girls (11-14 years)  enrolled for ICDS services'},
                    {'html': 38, 'sort_key': 38},
                    {'html': 34, 'sort_key': 34},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'header': 'Adolescent girls (11-14 years)  enrolled for ICDS services',
                'slug': 'cases_person_adolescent_girls_11_14',
            }
        )

    def test_cases_person_adolescent_girls_15_18(self):
        self.assertDictEqual(
            self.get_data()['config']['sections'][0]['rows_config'][18],
            {
                'average': {
                    'html': 13,
                    'sort_key': 13
                },
                'data': [
                    {'html': 'Adolescent girls (15-18 years)  enrolled for ICDS services'},
                    {'html': 19, 'sort_key': 19},
                    {'html': 13, 'sort_key': 13},
                    {'html': 0}
                ],
                'data_source': 'AggAWCMonthlyDataSource',
                'header': 'Adolescent girls (15-18 years)  enrolled for ICDS services',
                'slug': 'cases_person_adolescent_girls_15_18',
            }
        )

    def test_rest_of_data(self):
        data = self.get_data()
        del (data['config']['sections'][0]['rows_config'])
        self.assertDictEqual(
            data,
            {
                'config': {
                    'category': 'demographics',
                    'sections': [
                        {
                            'months': ['Apr 2017', 'May 2017', 'Jun 2017'],
                            'order': 4,
                            'section_title': 'Demographics',
                            'slug': 'demographics'
                        }
                    ],
                    'title': 'Demographics'
                }
            }
        )
