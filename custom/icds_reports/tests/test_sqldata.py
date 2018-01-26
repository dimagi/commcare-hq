from __future__ import absolute_import

from datetime import datetime
from django.test.testcases import TestCase
from custom.icds_reports.views import FactSheetsReport
from custom.icds_reports.utils import get_location_level


class TestExportData(TestCase):
    maxDiff = None

    def test_children_export(self):
        config = {
            'aggregation_level': 1,
            'month': datetime(2017, 6, 1).date(),
            'previous_month': datetime(2017, 5, 1).date(),
            'two_before': datetime(2017, 4, 1).date(),
            'category': 'maternal_and_child_nutrition',
            'domain': 'icds-cas'
        }

        loc_level = get_location_level(config.get('aggregation_level'))
        data = FactSheetsReport(config=config, loc_level=loc_level).get_data()

        self.assertDictEqual(
            data['config']['sections'][0]['rows_config'][0],
            {'average': {'html': 68.97066136250622, 'sort_key': 68.97066136250622},
             'data': [{'html': 'Weighing Efficiency (Children <5 weighed)'},
                      {'html': 67.61252446183953, 'sort_key': 67.61252446183953},
                      {'html': 70.37411526794742, 'sort_key': 70.37411526794742},
                      {'html': 0}],
             'data_source': 'AggChildHealthMonthlyDataSource',
             'format': 'percent',
             'header': 'Weighing Efficiency (Children <5 weighed)',
             'slug': 'status_weighed'}
        )
        self.assertDictEqual(
            data['config']['sections'][0]['rows_config'][1],
            {'data': [{'html': 'Total number of unweighed children (0-5 Years)'},
                      {'html': 331L, 'sort_key': 331L},
                      {'html': 293L, 'sort_key': 293L},
                      {'html': 0}],
             'data_source': 'AggChildHealthMonthlyDataSource',
             'header': 'Total number of unweighed children (0-5 Years)',
             'reverseColors': True,
             'slug': 'nutrition_status_unweighed'}
        )
        self.assertDictEqual(
            data['config']['sections'][0]['rows_config'][2],
            {'average': {'html': 2.523431867339582, 'sort_key': 2.523431867339582},
             'data': [{'html': 'Children from 0 - 5 years who are severely underweight (weight-for-age)'},
                      {'html': 2.170767004341534, 'sort_key': 2.170767004341534},
                      {'html': 2.8735632183908044, 'sort_key': 2.8735632183908044},
                      {'html': 0}],
             'data_source': 'AggChildHealthMonthlyDataSource',
             'format': 'percent',
             'header': 'Children from 0 - 5 years who are severely underweight (weight-for-age)',
             'reverseColors': True,
             'slug': 'severely_underweight'}
        )
        self.assertDictEqual(
            data['config']['sections'][0]['rows_config'][3],
            {'average': {'html': 20.90843547224225, 'sort_key': 20.90843547224225},
             'data': [{'html': 'Children from 0-5 years who are moderately underweight (weight-for-age)'},
                      {'html': 23.154848046309695, 'sort_key': 23.154848046309695},
                      {'html': 18.67816091954023, 'sort_key': 18.67816091954023},
                      {'html': 0}],
             'data_source': 'AggChildHealthMonthlyDataSource',
             'format': 'percent',
             'header': 'Children from 0-5 years who are moderately underweight (weight-for-age)',
             'reverseColors': True,
             'slug': 'moderately_underweight'}
        )
        self.assertDictEqual(
            data['config']['sections'][0]['rows_config'][4],
            {'average': {'html': 76.56813266041817, 'sort_key': 76.56813266041817},
             'data': [{'html': 'Children from 0-5 years who are at normal weight-for-age'},
                      {'html': 74.67438494934876, 'sort_key': 74.67438494934876},
                      {'html': 78.44827586206897, 'sort_key': 78.44827586206897},
                      {'html': 0}],
             'data_source': 'AggChildHealthMonthlyDataSource',
             'format': 'percent',
             'header': 'Children from 0-5 years who are at normal weight-for-age',
             'slug': 'status_normal'}
        )
        self.assertDictEqual(
            data['config']['sections'][0]['rows_config'][5],
            {'average': {'html': 0.05254860746190226, 'sort_key': 0.05254860746190226},
             'data': [{'html': 'Children from 6 - 60 months with severe acute malnutrition (weight-for-height)'},
                      {'html': 0.1037344398340249, 'sort_key': 0.1037344398340249},
                      {'html': 0.0, 'sort_key': 0.0},
                      {'html': 0}],
             'data_source': 'AggChildHealthMonthlyDataSource',
             'format': 'percent',
             'header': 'Children from 6 - 60 months with severe acute malnutrition (weight-for-height)',
             'reverseColors': True,
             'slug': 'wasting_severe'}
        )
        self.assertDictEqual(
            data['config']['sections'][0]['rows_config'][6],
            {'average': {'html': 0.4729374671571203, 'sort_key': 0.4729374671571203},
             'data': [{'html': 'Children from 6 - 60 months with moderate acute malnutrition (weight-for-height)'},
                      {'html': 0.1037344398340249, 'sort_key': 0.1037344398340249},
                      {'html': 0.8519701810436635, 'sort_key': 0.8519701810436635},
                      {'html': 0}],
             'data_source': 'AggChildHealthMonthlyDataSource',
             'format': 'percent',
             'header': 'Children from 6 - 60 months with moderate acute malnutrition (weight-for-height)',
             'reverseColors': True,
             'slug': 'wasting_moderate'}
        )
        self.assertDictEqual(
            data['config']['sections'][0]['rows_config'][7],
            {'average': {'html': 1.3137151865475565, 'sort_key': 1.3137151865475565},
             'data': [{'html': 'Children from 6 - 60 months with normal weight-for-height'},
                      {'html': 0.6224066390041494, 'sort_key': 0.6224066390041494},
                      {'html': 2.0234291799787005, 'sort_key': 2.0234291799787005},
                      {'html': 0}],
             'data_source': 'AggChildHealthMonthlyDataSource',
             'format': 'percent',
             'header': 'Children from 6 - 60 months with normal weight-for-height',
             'slug': 'wasting_normal'}
        )
        self.assertDictEqual(
            data['config']['sections'][0]['rows_config'][8],
            {'average': {'html': 0.8407777193904361, 'sort_key': 0.8407777193904361},
             'data': [{'html': 'Children from 6 - 60 months with severe stunting (height-for-age)'},
                      {'html': 0.5186721991701245, 'sort_key': 0.5186721991701245},
                      {'html': 1.1714589989350372, 'sort_key': 1.1714589989350372},
                      {'html': 0}],
             'data_source': 'AggChildHealthMonthlyDataSource',
             'format': 'percent',
             'header': 'Children from 6 - 60 months with severe stunting (height-for-age)',
             'reverseColors': True,
             'slug': 'stunting_severe'}
        )
        self.assertDictEqual(
            data['config']['sections'][0]['rows_config'][9],
            {'average': {'html': 0.6305832895428272, 'sort_key': 0.6305832895428272},
             'data': [{'html': 'Children from 6 - 60 months with moderate stunting (height-for-age)'},
                      {'html': 0.4149377593360996, 'sort_key': 0.4149377593360996},
                      {'html': 0.8519701810436635, 'sort_key': 0.8519701810436635},
                      {'html': 0}],
             'data_source': 'AggChildHealthMonthlyDataSource',
             'format': 'percent',
             'header': 'Children from 6 - 60 months with moderate stunting (height-for-age)',
             'reverseColors': True,
             'slug': 'stunting_moderate'}
        )
        self.assertDictEqual(
            data['config']['sections'][0]['rows_config'][10],
            {'average': {'html': 0.7882291119285338, 'sort_key': 0.7882291119285338},
             'data': [{'html': 'Children from 6 - 60 months with normal height-for-age'},
                      {'html': 0.2074688796680498, 'sort_key': 0.2074688796680498},
                      {'html': 1.384451544195953, 'sort_key': 1.384451544195953},
                      {'html': 0}],
             'data_source': 'AggChildHealthMonthlyDataSource',
             'format': 'percent',
             'header': 'Children from 6 - 60 months with normal height-for-age',
             'slug': 'stunting_normal'}
        )
        self.assertDictEqual(
            data['config']['sections'][0]['rows_config'][11],
            {'average': {'html': 66.66666666666667, 'sort_key': 66.66666666666667},
             'data': [{'html': 'Percent of children born in month with low birth weight'},
                      {'html': 0.0, 'sort_key': 0.0},
                      {'html': 66.66666666666667, 'sort_key': 66.66666666666667},
                      {'html': 0}],
             'data_source': 'AggChildHealthMonthlyDataSource',
             'format': 'percent',
             'header': 'Percent of children born in month with low birth weight',
             'slug': 'low_birth_weight'}
        )

        # compare rest of retrieved data
        del(data['config']['sections'][0]['rows_config'])
        self.assertDictEqual(
            data,
            {'config': {'category': 'maternal_and_child_nutrition',
                        'sections': [{'months': ['Apr 2017', 'May 2017', 'Jun 2017'],
                                      'order': 1,
                                      'section_title': 'Nutrition Status of Children',
                                      'slug': 'nutrition_status_of_children'}],
                        'title': 'Maternal and Child Nutrition'}}
        )
