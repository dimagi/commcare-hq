from datetime import datetime
from django.test import SimpleTestCase, TestCase
from corehq.apps.reports.models import ReportNotification
from corehq.apps.reports.scheduled import guess_reporting_minute, get_scheduled_reports
from corehq.apps.reports.tasks import get_report_queue


class GuessReportingMinuteTest(SimpleTestCase):

    def testOnTheHour(self):
        self.assertEqual(0, guess_reporting_minute(datetime(2014, 10, 31, 12, 0)))

    def testAfterTheHour(self):
        self.assertEqual(0, guess_reporting_minute(datetime(2014, 10, 31, 12, 5)))

    def testOnTheHalfHour(self):
        self.assertEqual(30, guess_reporting_minute(datetime(2014, 10, 31, 12, 30)))

    def testAfterTheHalfHour(self):
        self.assertEqual(30, guess_reporting_minute(datetime(2014, 10, 31, 12, 35)))

    def testOutOfBounds(self):
        for minute in (6, 15, 29, 36, 45, 59):
            self.assertRaises(ValueError, guess_reporting_minute, datetime(2014, 10, 31, 12, minute))


class ScheduledReportTest(TestCase):

    def setUp(self):
        for report in ReportNotification.view(
            'reportconfig/all_notifications',
            include_docs=True,
            reduce=False,
        ).all():
            report.delete()

    def _check(self, period, as_of, count):
        self.assertEqual(count, len(list(get_scheduled_reports(period, as_of))))

    def testDefaultValue(self):
        now = datetime.utcnow()
        ReportNotification(hour=now.hour, minute=(now.minute / 30) * 30, interval='daily').save()
        if now.minute % 30 <= 5:
            self._check('daily', None, 1)
        else:
            self.assertRaises(
                ValueError,
                lambda: list(get_scheduled_reports('daily', None))
            )

    def testDailyReportEmptyMinute(self):
        ReportNotification(hour=12, minute=None, interval='daily').save()
        self._check('daily', datetime(2014, 10, 31, 12, 0), 1)
        self._check('daily', datetime(2014, 10, 31, 12, 30), 0)  # half hour shouldn't count

    def testDailyReportWithMinute(self):
        ReportNotification(hour=12, minute=0, interval='daily').save()
        self._check('daily', datetime(2014, 10, 31, 12, 0), 1)
        self._check('daily', datetime(2014, 10, 31, 12, 30), 0)

    def testDailyReportLenientWindow(self):
        ReportNotification(hour=12, minute=0, interval='daily').save()
        self._check('daily', datetime(2014, 10, 31, 12, 5), 1)  # lenient window
        # but not too lenient
        self.assertRaises(
            ValueError,
            lambda: list(get_scheduled_reports('daily', datetime(2014, 10, 31, 12, 6)))
        )

    def testDailyReportWithMinuteHalfHour(self):
        ReportNotification(hour=12, minute=30, interval='daily').save()
        self._check('daily', datetime(2014, 10, 31, 12, 0), 0)
        self._check('daily', datetime(2014, 10, 31, 12, 30), 1)

    def testDailyReportOtherTypesDontCount(self):
        ReportNotification(hour=12, minute=0, day=31, interval='daily').save()
        self._check('weekly', datetime(2014, 10, 31, 12, 0), 0)
        self._check('n_weeks', datetime(2014, 10, 31, 12, 0), 0)
        self._check('monthly', datetime(2014, 10, 31, 12, 0), 0)

    def testDailyReportOtherHoursDontCount(self):
        ReportNotification(hour=12, minute=0, day=31, interval='daily').save()
        self._check('daily', datetime(2014, 10, 31, 11, 0), 0)

    def testWeeklyReportEmptyMinute(self):
        ReportNotification(hour=12, minute=None, day=4, interval='weekly').save()
        self._check('weekly', datetime(2014, 10, 31, 12, 0), 1)
        self._check('weekly', datetime(2014, 10, 31, 12, 30), 0)  # half hour shouldn't count

    def testWeeklyReportWithMinute(self):
        ReportNotification(hour=12, minute=0, day=4, interval='weekly').save()
        self._check('weekly', datetime(2014, 10, 31, 12, 0), 1)
        self._check('weekly', datetime(2014, 10, 31, 12, 30), 0)

    def testWeeklyReportOtherTypesDontCount(self):
        ReportNotification(hour=12, minute=0, day=4, interval='weekly').save()
        self._check('daily', datetime(2014, 10, 31, 12, 0), 0)
        self._check('n_weeks', datetime(2014, 10, 31, 12, 0), 0)
        self._check('monthly', datetime(2014, 10, 31, 12, 0), 0)

    def testWeeklyReportOtherDaysDontCount(self):
        ReportNotification(hour=12, minute=0, day=4, interval='weekly').save()
        self._check('weekly', datetime(2014, 10, 30, 12, 0), 0)

    def testNWeeksReportEmptyMinute(self):
        ReportNotification(hour=12, minute=None, day=4, interval='n_weeks', n_weeks=3, offset_weeks=2).save()
        self._check('n_weeks', datetime(2014, 10, 17, 12, 0), 0)
        self._check('n_weeks', datetime(2014, 10, 24, 12, 0), 0)
        self._check('n_weeks', datetime(2014, 10, 31, 12, 0), 1)
        self._check('n_weeks', datetime(2014, 11, 1, 12, 0), 0)

    def testNWeeksReportWithMinute(self):
        ReportNotification(hour=12, minute=0, day=4, interval='n_weeks', n_weeks=3, offset_weeks=2).save()
        self._check('n_weeks', datetime(2014, 10, 17, 12, 0), 0)
        self._check('n_weeks', datetime(2014, 10, 24, 12, 0), 0)
        self._check('n_weeks', datetime(2014, 10, 31, 12, 0), 1)
        self._check('n_weeks', datetime(2014, 11, 1, 12, 0), 0)

        self._check('n_weeks', datetime(2014, 10, 17, 12, 30), 0)
        self._check('n_weeks', datetime(2014, 10, 24, 12, 30), 0)
        self._check('n_weeks', datetime(2014, 10, 31, 12, 30), 0)
        self._check('n_weeks', datetime(2014, 11, 1, 12, 30), 0)

    def testNWeeksReportOtherTypesDontCount(self):
        ReportNotification(hour=12, minute=0, day=4, interval='n_weeks', n_weeks=3, offset_weeks=2).save()
        for period in ['daily', 'weekly', 'monthly']:
            self._check(period, datetime(2014, 10, 30, 12, 0), 0)

    def testMonthlyReportEmptyMinute(self):
        ReportNotification(hour=12, minute=None, day=31, interval='monthly').save()
        self._check('monthly', datetime(2014, 10, 31, 12, 0), 1)
        self._check('monthly', datetime(2014, 10, 31, 12, 30), 0)  # half hour shouldn't count

    def testMonthlyReportWithMinute(self):
        ReportNotification(hour=12, minute=0, day=31, interval='monthly').save()
        self._check('monthly', datetime(2014, 10, 31, 12, 0), 1)
        self._check('monthly', datetime(2014, 10, 31, 12, 30), 0)

    def testMonthlyReportOtherTypesDontCount(self):
        ReportNotification(hour=12, minute=None, day=31, interval='monthly').save()
        self._check('daily', datetime(2014, 10, 31, 12, 0), 0)
        self._check('weekly', datetime(2014, 10, 31, 12, 0), 0)
        self._check('n_weeks', datetime(2014, 10, 31, 12, 0), 0)

    def testMonthlyReportOtherDaysDontCount(self):
        ReportNotification(hour=12, minute=None, day=31, interval='monthly').save()
        self._check('monthly', datetime(2014, 10, 30, 12, 0), 0)

    def testMonthlyReportOnTheEndOfTheMonthEmptyMinute(self):
        ReportNotification(hour=12, minute=None, day=30, interval='monthly').save()
        ReportNotification(hour=12, minute=None, day=31, interval='monthly').save()
        self._check('monthly', datetime(2014, 11, 30, 12, 0), 2)

    def testMonthlyReportOnTheEndOfTheMonthWithMinute(self):
        ReportNotification(hour=12, minute=0, day=30, interval='monthly').save()
        ReportNotification(hour=12, minute=0, day=31, interval='monthly').save()
        self._check('monthly', datetime(2014, 11, 30, 12, 0), 2)

    def testMonthlyReportOnTheEndOfTheMonthWithMinuteHalfHour(self):
        ReportNotification(hour=12, minute=30, day=30, interval='monthly').save()
        ReportNotification(hour=12, minute=30, day=31, interval='monthly').save()
        self._check('monthly', datetime(2014, 11, 30, 12, 30), 2)

    def testMonthlyReportBeforeTheEndOfTheMonth(self):
        ReportNotification(hour=12, minute=None, day=30, interval='monthly').save()
        ReportNotification(hour=12, minute=None, day=31, interval='monthly').save()
        self._check('monthly', datetime(2014, 10, 30, 12, 0), 1)

    def testMonthlyReportOnTheEndOfTheMonthDaysAfter31DontCount(self):
        ReportNotification(hour=12, minute=None, day=31, interval='monthly').save()
        ReportNotification(hour=12, minute=None, day=32, interval='monthly').save()
        self._check('monthly', datetime(2014, 10, 31, 12, 0), 1)


class TestMVPCeleryQueueHack(SimpleTestCase):

    def test_queue_selection_mvp(self):
        self.assertEqual('background_queue', get_report_queue(ReportNotification(domain='mvp-tiby')))

    def test_queue_selection_normal(self):
        self.assertEqual('celery', get_report_queue(ReportNotification(domain='not-mvp')))
