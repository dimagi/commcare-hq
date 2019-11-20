import uuid
from unittest.mock import patch

from django.core import management
from django.test import TestCase

from corehq.util.test_utils import generate_cases
from custom.icds_reports.models.util import AggregationRecord


class TestPreviousMonthSkipping(TestCase):
    def _test_prev_month(self, date_string, prev_month_called):
        prev_month_agg_uuid = uuid.uuid4().hex

        # verify that setup_aggregation is only run when previous month should be run
        with patch(
                'custom.icds_reports.management.commands.create_aggregation_record.setup_aggregation',
                return_value=None) as mock_setup:
            management.call_command('create_aggregation_record', prev_month_agg_uuid, date_string, -1)
        if prev_month_called:
            mock_setup.assert_called_once()
            self.assertTrue(AggregationRecord.objects.get(agg_uuid=prev_month_agg_uuid).run_aggregation_queries)
        else:
            mock_setup.assert_not_called()
            self.assertFalse(AggregationRecord.objects.get(agg_uuid=prev_month_agg_uuid).run_aggregation_queries)

        # verify that a step in the aggregation is only run when previous month should be run
        with patch(
                'custom.icds_reports.management.commands.run_aggregation_query.run_task',
                return_value=None) as mock_update:
            management.call_command(
                'run_aggregation_query',
                'update_child_health_monthly_table',
                prev_month_agg_uuid)
        if prev_month_called:
            mock_update.assert_called_once()
            self.assertTrue(AggregationRecord.objects.get(agg_uuid=prev_month_agg_uuid).run_aggregation_queries)
        else:
            mock_update.assert_not_called()
            self.assertFalse(AggregationRecord.objects.get(agg_uuid=prev_month_agg_uuid).run_aggregation_queries)

    def _test_current_month(self, date_string):
        agg_uuid = uuid.uuid4().hex

        # verify that a setup aggregation is always run
        with patch(
                'custom.icds_reports.management.commands.create_aggregation_record.setup_aggregation',
                return_value=None) as mock_setup:
            management.call_command('create_aggregation_record', agg_uuid, date_string, 0)
        mock_setup.assert_called_once()
        self.assertTrue(AggregationRecord.objects.get(agg_uuid=agg_uuid).run_aggregation_queries)

        # verify that a step in the aggregation is always run
        with patch(
                'custom.icds_reports.management.commands.run_aggregation_query.run_task',
                return_value=None) as mock_update:
            management.call_command('run_aggregation_query', 'update_child_health_monthly_table', agg_uuid)
        mock_update.assert_called_once()
        self.assertTrue(AggregationRecord.objects.get(agg_uuid=agg_uuid).run_aggregation_queries)


@generate_cases([
    ("2019-11-01", True),
    ("2019-11-02", True),
    ("2019-11-03", True),
    ("2019-11-04", False),
    ("2019-11-05", False),
    ("2019-11-06", False),
    ("2019-11-07", False),
    ("2019-11-08", False),
    ("2019-11-09", True),  # Saturday
    ("2019-11-10", False),
    ("2019-11-11", True),  # AWW performance report
    ("2019-11-12", False),
    ("2019-11-13", False),
    ("2019-11-14", False),
    ("2019-11-15", False),
    ("2019-11-16", True),  # Saturday
    ("2019-11-17", False),
    ("2019-11-18", False),
    ("2019-11-19", False),
    ("2019-11-20", False),
    ("2019-11-21", False),
    ("2019-11-22", False),
    ("2019-11-23", True),  # Saturday
    ("2019-11-24", False),
    ("2019-11-25", False),
    ("2019-11-26", False),
    ("2019-11-27", False),
    ("2019-11-28", False),
    ("2019-11-29", False),
    ("2019-11-30", True),
], TestPreviousMonthSkipping)
def test_agg_should_run(self, date_string, prev_month_called):
    self._test_prev_month(date_string, prev_month_called)
    self._test_current_month(date_string)
