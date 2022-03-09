from django.test import TestCase
from ..logging import ScheduledReportLogger
from ..models import ReportNotification, ScheduledReportLog


class ScheduledReportLoggerTests(TestCase):
    UUID_LENGTH = 32
    REPORT_ID = 'a' * UUID_LENGTH

    def setUp(self):
        self.report = ReportNotification(
            _id=self.REPORT_ID,
            owner_id='5',
            domain='test_domain',
            recipient_emails=[])

    def test_success_logs_and_stores_db_record(self):
        with self.assertLogs(level='INFO') as cm:
            ScheduledReportLogger.log_email_success(self.report, 'test@dimagi.com', 'test_body')
            self.assertIn(
                f'Sent email for scheduled report {self.REPORT_ID} to test@dimagi.com. '
                'Details: Domain: test_domain, bytes: 9',
                cm.output[0])

        report_log = ScheduledReportLog.objects.get(report_id=self.REPORT_ID)
        self.assertEqual(report_log.sent_to, 'test@dimagi.com')
        self.assertEqual(report_log.domain, 'test_domain')
        self.assertEqual(report_log.state, 'success')
        self.assertEqual(report_log.size, 9)
        self.assertIsNone(report_log.error)

    def test_failure_logs_and_stores_db_record(self):
        with self.assertLogs(level='ERROR') as cm:
            ScheduledReportLogger.log_email_failure(self.report,
                'test@dimagi.com', 'test_body', Exception('Error!'))
            self.assertIn(
                f'Encountered error while sending report {self.REPORT_ID} to test@dimagi.com. Details: '
                f'Domain: test_domain, bytes: 9. Error: Error!',
                cm.output[0])

        report_log = ScheduledReportLog.objects.get(report_id=self.REPORT_ID)
        self.assertEqual(report_log.sent_to, 'test@dimagi.com')
        self.assertEqual(report_log.domain, 'test_domain')
        self.assertEqual(report_log.state, 'error')
        self.assertEqual(report_log.size, 9)
        self.assertEqual(report_log.error, 'Error!')

    def test_retry_logs_and_stores_db_record(self):
        with self.assertLogs(level='INFO') as cm:
            ScheduledReportLogger.log_email_size_failure(self.report,
                'test1@dimagi.com', ['test1@dimagi.com', 'test2@dimagi.com'], 'test_body')
            self.assertIn(
                f'Email for scheduled report {self.REPORT_ID} to test1@dimagi.com failed due to size. Details: '
                'Domain: test_domain, bytes: 9. Attempting to send as attachments to '
                'test1@dimagi.com, test2@dimagi.com',
                cm.output[0])

        report_log = ScheduledReportLog.objects.get(report_id=self.REPORT_ID)
        self.assertEqual(report_log.sent_to, 'test1@dimagi.com')
        self.assertEqual(report_log.domain, 'test_domain')
        self.assertEqual(report_log.state, 'retry')
        self.assertEqual(report_log.size, 9)
        self.assertEqual(report_log.error, 'size')
