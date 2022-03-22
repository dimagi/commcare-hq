import datetime
from dataclasses import dataclass
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from freezegun import freeze_time

from .. import tasks
from ..exceptions import ReportNotFound
from ..models import ScheduledReportLog
from ..tasks import (
    purge_old_scheduled_report_logs,
    queue_scheduled_reports,
    send_email_report,
)

CURRENT_DATE = datetime.date(2020, 1, 2)


@freeze_time(CURRENT_DATE)
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


class TestSendEmailReport(SimpleTestCase):

    def test_duplicates(self):
        recipient_list = [
            'alice@example.com',
            'alice@example.com',
            'alice@example.com',
        ]
        request_data = {
            'couch_user': 'abc123',
            'GET': {
                'startdate': '2022-01-01T00:00:00Z',
                'enddate': '2022-01-31T23:59:59Z',
            }
        }
        with patch('corehq.apps.saved_reports.tasks.CouchUser', CouchUser), \
                patch('corehq.apps.reports.views._render_report_configs') as render_configs, \
                patch('corehq.apps.reports.views.render_full_report_notification') as render_report, \
                patch('corehq.apps.saved_reports.tasks.send_HTML_email') as send_html_email:
            render_configs.return_value = ['report_text']
            render_report.return_value = ReportNotification('content')

            send_email_report(
                recipient_list,
                'test-domain',
                'report_slug',
                'report_type',
                request_data,
                is_once_off=True,
                subject='',
                notes='',
            )

            send_html_email.assert_called_once()


@dataclass
class CouchUser:
    user_id: str
    language: str

    @classmethod
    def get_by_user_id(cls, user_id):
        return cls(
            user_id=user_id,
            language='tnq',
        )


@dataclass
class ReportNotification:
    content: str
