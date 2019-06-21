from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from datetime import datetime, timedelta
from django.test import SimpleTestCase, TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.saved_reports.models import ReportConfig, ReportNotification
from corehq.apps.saved_reports.scheduled import guess_reporting_minute, get_scheduled_report_ids
from corehq.apps.reports.views import get_scheduled_report_response
from corehq.apps.users.models import WebUser


class GuessReportingMinuteTest(SimpleTestCase):

    def testOnTheHour(self):
        self.assertEqual(0, guess_reporting_minute(datetime(2014, 10, 31, 12, 0)))

    def testAfterTheHour(self):
        self.assertEqual(0, guess_reporting_minute(datetime(2014, 10, 31, 12, 5)))

    def testOnTheHalfHour(self):
        self.assertEqual(30, guess_reporting_minute(datetime(2014, 10, 31, 12, 30)))

    def testAfterTheHalfHour(self):
        self.assertEqual(30, guess_reporting_minute(datetime(2014, 10, 31, 12, 35)))

    def testOnQuarterAfter(self):
        self.assertEqual(15, guess_reporting_minute(datetime(2014, 10, 31, 12, 15)))

    def testAfterQuarterAfter(self):
        self.assertEqual(15, guess_reporting_minute(datetime(2014, 10, 31, 12, 20)))

    def testOnQuarterOf(self):
        self.assertEqual(45, guess_reporting_minute(datetime(2014, 10, 31, 12, 45)))

    def testAfterQuarterOf(self):
        self.assertEqual(45, guess_reporting_minute(datetime(2014, 10, 31, 12, 50)))

    def testOutOfBounds(self):
        for minute in (6, 14, 21, 29, 36, 44, 51, 59):
            self.assertRaises(ValueError, guess_reporting_minute, datetime(2014, 10, 31, 12, minute))


def delete_all_report_notifications():
    for report in ReportNotification.view(
            'reportconfig/all_notifications',
            include_docs=True,
            reduce=False,
    ).all():
        report.delete()


class ScheduledReportTest(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        delete_all_report_notifications()

    def _check(self, period, as_of, count):
        # get_scheduled_report_ids relies on end_datetime
        # being strictly greater than start_datetime
        # for tests targeting an exact minute mark,
        # we need to add a small amount to make it after.
        # This is a reasonable thing to do because in production,
        # it'll always run a short time after the periodic task is fired
        as_of += timedelta(microseconds=1)
        self.assertEqual(count, len(list(get_scheduled_report_ids(period, end_datetime=as_of))))

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
            lambda: list(get_scheduled_report_ids('daily', end_datetime=datetime(2014, 10, 31, 12, 6)))
        )

    def testDailyReportWithMinuteHalfHour(self):
        ReportNotification(hour=12, minute=30, interval='daily').save()
        self._check('daily', datetime(2014, 10, 31, 12, 0), 0)
        self._check('daily', datetime(2014, 10, 31, 12, 30), 1)

    def testDailyReportOtherTypesDontCount(self):
        ReportNotification(hour=12, minute=0, day=31, interval='daily').save()
        self._check('weekly', datetime(2014, 10, 31, 12, 0), 0)
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
        self._check('monthly', datetime(2014, 10, 31, 12, 0), 0)

    def testWeeklyReportOtherDaysDontCount(self):
        ReportNotification(hour=12, minute=0, day=4, interval='weekly').save()
        self._check('weekly', datetime(2014, 10, 30, 12, 0), 0)

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


class ScheduledReportSendingTest(TestCase):

    domain = 'test-scheduled-reports'

    @classmethod
    def setUpClass(cls):
        super(ScheduledReportSendingTest, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.user = WebUser.create(
            domain=cls.domain,
            username='dummy@example.com',
            password='secret',
        )

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        cls.user.delete()
        delete_all_report_notifications()
        super(ScheduledReportSendingTest, cls).tearDownClass()

    def test_get_scheduled_report_response(self):
        domain = self.domain
        report_config = ReportConfig.wrap({
            "date_range": "last30",
            "days": 30,
            "domain": domain,
            "report_slug": "worker_activity",
            "report_type": "project_report",
            "owner_id": self.user._id,
        })
        report_config.save()
        report = ReportNotification(
            hour=12, minute=None, day=30, interval='monthly', config_ids=[report_config._id]
        )
        report.save()
        response = get_scheduled_report_response(
            couch_user=self.user, domain=domain, scheduled_report_id=report._id
        )[0]
        self.assertTrue(self.user.username in response.decode('utf-8'))
