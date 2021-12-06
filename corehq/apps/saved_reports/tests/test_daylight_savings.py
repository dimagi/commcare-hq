from django.test import SimpleTestCase
from corehq.apps.saved_reports.management.commands.daylight_savings import adjust_report

from ..models import ReportNotification


class AdjustReportTests(SimpleTestCase):
    def test_moves_report_hour_back(self):
        report = ReportNotification(hour=1, minute=5, day=4, interval='daily')
        adjust_report(report, forward=False)
        self.assertEqual(report.hour, 0)

    def test_moves_report_hour_forward(self):
        report = ReportNotification(hour=1, minute=5, day=4, interval='daily')
        adjust_report(report, forward=True)
        self.assertEqual(report.hour, 2)

    def test_wraps_hour_backwards(self):
        report = ReportNotification(hour=0, minute=5, day=4, interval='daily')
        adjust_report(report, forward=False)
        self.assertEqual(report.hour, 23)

    def test_wraps_hour_forwards(self):
        report = ReportNotification(hour=23, minute=5, day=4, interval='daily')
        adjust_report(report, forward=True)
        self.assertEqual(report.hour, 0)

    def test_wrapping_daily_does_not_increment_day(self):
        report = ReportNotification(hour=23, minute=5, day=4, interval='daily')
        adjust_report(report, forward=True)
        self.assertEqual(report.day, 4)

    def test_increments_day_on_weekly_wrap(self):
        report = ReportNotification(hour=23, minute=5, day=4, interval='weekly')
        adjust_report(report, forward=True)
        self.assertEqual(report.day, 5)

    def test_wraps_day_on_weekly(self):
        report = ReportNotification(hour=23, minute=5, day=6, interval='weekly')
        adjust_report(report, forward=True)
        self.assertEqual(report.day, 0)

    def test_handles_weekly_mondays(self):
        report = ReportNotification(hour=23, minute=5, day=0, interval='weekly')
        adjust_report(report, forward=True)
        # Ensure does not throw
