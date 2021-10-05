from django.test import TestCase
from freezegun import freeze_time
import datetime

from ..models import ScheduledReportLog
from ..tasks import purge_old_scheduled_report_logs


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
