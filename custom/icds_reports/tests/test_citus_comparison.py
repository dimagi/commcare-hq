from __future__ import absolute_import, unicode_literals

from datetime import datetime

from django.test import TestCase

from mock import patch

from corehq.util.test_utils import flag_disabled, flag_enabled
from custom.icds_reports.models import AggAwc
from custom.icds_reports.utils import get_location_level
from custom.icds_reports.views import FactSheetsReport


class TestDjango(TestCase):
    @flag_disabled('ICDS_COMPARE_QUERIES_AGAINST_CITUS')
    @patch('custom.icds_reports.utils.tasks.call_citus_experiment')
    def test_compare_not_called(self, experiment):
        list(AggAwc.objects.values('awc_id'))
        experiment.assert_not_called()

    @flag_enabled('ICDS_COMPARE_QUERIES_AGAINST_CITUS')
    @patch('custom.icds_reports.utils.tasks.call_citus_experiment')
    def test_compare_called_no_filter(self, experiment):
        list(AggAwc.objects.values('awc_id'))
        self.assertEqual(len(experiment.call_args_list), 1)
        call = experiment.call_args_list[0]
        self.assertEqual(call[0][0], 'SELECT "agg_awc"."awc_id" FROM "agg_awc"')
        self.assertEqual(call[0][1], [])
        self.assertEqual(call[1]['data_source'], 'AggAwc')

    @flag_enabled('ICDS_COMPARE_QUERIES_AGAINST_CITUS')
    @patch('custom.icds_reports.utils.tasks.call_citus_experiment')
    def test_compare_called_with_filter(self, experiment):
        list(AggAwc.objects.filter(aggregation_level=4, supervisor_id='super').values('awc_id'))
        self.assertEqual(len(experiment.call_args_list), 1)
        call = experiment.call_args_list[0]
        self.assertIn('SELECT "agg_awc"."awc_id" FROM "agg_awc"', call[0][0])
        self.assertIn('"agg_awc"."supervisor_id" = %s', call[0][0])
        self.assertIn('"agg_awc"."aggregation_level" = %s', call[0][0])
        self.assertIn('super', call[0][1])
        self.assertIn(4, call[0][1])
        self.assertEqual(call[1]['data_source'], 'AggAwc')


class TestSqlData(TestCase):
    @flag_disabled('ICDS_COMPARE_QUERIES_AGAINST_CITUS')
    @patch('custom.icds_reports.sqldata.base.call_citus_experiment')
    def test_compare_not_called(self, experiment):
        config = {
            'aggregation_level': 1,
            'month': datetime(2017, 6, 1).date(),
            'previous_month': datetime(2017, 5, 1).date(),
            'two_before': datetime(2017, 4, 1).date(),
            'category': 'maternal_and_child_nutrition',
            'domain': 'icds-cas'
        }

        loc_level = get_location_level(config.get('aggregation_level'))
        FactSheetsReport(config=config, loc_level=loc_level).get_data()
        experiment.assert_not_called()

    @flag_enabled('ICDS_COMPARE_QUERIES_AGAINST_CITUS')
    @patch('custom.icds_reports.sqldata.base.call_citus_experiment')
    def test_compare_called(self, experiment):
        config = {
            'aggregation_level': 1,
            'month': datetime(2017, 6, 1).date(),
            'previous_month': datetime(2017, 5, 1).date(),
            'two_before': datetime(2017, 4, 1).date(),
            'category': 'maternal_and_child_nutrition',
            'domain': 'icds-cas'
        }

        loc_level = get_location_level(config.get('aggregation_level'))
        FactSheetsReport(config=config, loc_level=loc_level).get_data()
        self.assertEqual(len(experiment.call_args_list), 2)

        second_call = experiment.call_args_list[1]
        self.assertEqual(
            second_call[0][1],
            {
                'domain': 'icds-cas',
                'age_12': '12',
                'age_72': '72',
                'previous_month': '2017-05-01',
                'age_24': '24',
                'age_36': '36',
                'age_48': '48',
                'age_60': '60',
                'age_0': '0',
                'aggregation_level': 1,
                'age_6': '6'
            },
        )
        self.assertEqual(second_call[1]['data_source'], 'NationalAggregationDataSource')

        # small selection of parts of query
        query = second_call[0][0]
        self.assertIn('sum(CASE WHEN age_tranche != %(age_72)s THEN wer_eligible END', query)
        self.assertIn('FROM agg_child_health_monthly', query)
        self.assertIn('WHERE aggregation_level = %(aggregation_level)s AND month = %(previous_month)s', query)
        self.assertIn('GROUP BY month', query)
