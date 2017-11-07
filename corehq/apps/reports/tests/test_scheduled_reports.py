from __future__ import absolute_import
from datetime import datetime
from django.test import SimpleTestCase, TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.reports.models import ReportNotification, ReportConfig
from corehq.apps.reports.scheduled import guess_reporting_minute, get_scheduled_report_ids
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


class ScheduledReportTest(TestCase):

    def setUp(self):
        for report in ReportNotification.view(
            'reportconfig/all_notifications',
            include_docs=True,
            reduce=False,
        ).all():
            report.delete()

    def _check(self, period, as_of, count):
        self.assertEqual(count, len(list(get_scheduled_report_ids(period, as_of))))

    def testDefaultValue(self):
        now = datetime.utcnow()
        # This line makes sure that the date of the ReportNotification is an increment of 15 minutes
        ReportNotification(hour=now.hour, minute=(now.minute / 15) * 15, interval='daily').save()
        if now.minute % 15 <= 5:
            self._check('daily', None, 1)
        else:
            self.assertRaises(
                ValueError,
                lambda: list(get_scheduled_report_ids('daily', None))
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
            lambda: list(get_scheduled_report_ids('daily', datetime(2014, 10, 31, 12, 6)))
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
        self.assertTrue(self.user.username in response)
