from unittest.mock import patch
from django.test import SimpleTestCase, TestCase
from time_machine import travel
import datetime

from ..exceptions import ReportNotFound
from ..models import ScheduledReportLog
from ..tasks import purge_old_scheduled_report_logs, queue_scheduled_reports
from .. import tasks


CURRENT_DATE = datetime.date(2020, 1, 2)


@travel(CURRENT_DATE, tick=False)
class PurgeOldScheduledReportLogsTests(TestCase):
    def test_purges_entries_older_than_three_months(self):
        self._create_log_at_date(CURRENT_DATE - datetime.timedelta(weeks=12, days=1))

        purge_old_scheduled_report_logs()

        count = ScheduledReportLog.objects.count()
        self.assertEqual(count, 0)

    def test_ignores_entries_newer_than_three_months(self):
        self._create_log_at_date(CURRENT_DATE - datetime.timedelta(weeks=12))

        purge_old_scheduled_report_logs()

        count = ScheduledReportLog.objects.count()
        self.assertEqual(count, 1)

    @staticmethod
    def _create_log_at_date(date):
        return ScheduledReportLog.objects.create(
            sent_to='test@dimagi.com',
            domain='test-domain',
            report_id='a' * 32,
            state='success',
            size=10,
            timestamp=date
        )


class QueueScheduledReportsTests(SimpleTestCase):
    @patch.object(tasks, 'send_delayed_report')
    @patch.object(tasks, 'create_records_for_scheduled_reports')
    def test_resource_not_found_does_not_stop_sending(self, mock_get_ids, mock_send):
        mock_get_ids.return_value = ['a', 'b', 'c']  # Expect to send these 3 reports
        mock_send.side_effect = ReportNotFound  # ...and have all of them throw ReportNotFound

        queue_scheduled_reports()

        # Verify that the 3 expected reports were attempted
        ARG_INDEX = 0
        calls = set(call[ARG_INDEX][0] for call in mock_send.call_args_list)
        self.assertSetEqual(calls, {'a', 'b', 'c'})
