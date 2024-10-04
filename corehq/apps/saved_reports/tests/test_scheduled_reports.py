from unittest.mock import patch

from datetime import datetime, timedelta

from django.test import SimpleTestCase, TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.cases import case_adapter
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.reports.views import get_scheduled_report_response
from corehq.apps.saved_reports.models import ReportConfig, ReportNotification
from corehq.apps.saved_reports.scheduled import (
    get_scheduled_report_ids,
    guess_reporting_minute,
)
from corehq.apps.users.models import HqPermissions, UserRole, WebUser


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

    def testHourlyReportWithMinuteZero(self):
        ReportNotification(hour=1, minute=0, interval='hourly').save()
        self._check('hourly', datetime(2014, 10, 31, 1, 0), 1)
        self._check('hourly', datetime(2014, 10, 31, 1, 30), 0)

    def testHourlyReportWithMinuteHalfHour(self):
        # We don't currently cater for minute-specific hourly reporting;
        # every report with 'hourly' interval will be sent on the zero-minute hour
        ReportNotification(hour=1, minute=30, interval='hourly').save()
        self._check('hourly', datetime(2014, 10, 31, 1, 0), 1)
        self._check('hourly', datetime(2014, 10, 31, 1, 30), 0)

    def testHourlyReportWithoutMinute(self):
        # We don't currently cater for minute-specific hourly reporting;
        # every report with 'hourly' interval will be sent on the zero-minute hour
        ReportNotification(hour=1, minute=None, interval='hourly').save()
        self._check('hourly', datetime(2014, 10, 31, 1, 0), 1)

    def testHourlyReportWithoutSpecifyingStopHour(self):
        ReportNotification(hour=0, interval='hourly').save()
        self._check('hourly', datetime(2014, 10, 31, 12, 0), 1)

    def testHourlyReportWithNoneStopHour(self):
        # It should return every hour if stop_hour not valid
        ReportNotification(hour=0, stop_hour=None, interval='hourly').save()
        self._check('hourly', datetime(2014, 10, 31, 12, 0), 1)

    def testHourlyReportWithInterval_everyHour(self):
        ReportNotification(hour=0, interval='hourly').save()
        self._check('hourly', datetime(2014, 10, 31, 0, 0), 1)
        self._check('hourly', datetime(2014, 10, 31, 1, 0), 1)
        self._check('hourly', datetime(2014, 10, 31, 7, 0), 1)
        self._check('hourly', datetime(2014, 10, 31, 18, 0), 1)
        self._check('hourly', datetime(2014, 10, 31, 23, 0), 1)

    def testHourlyReportWithInterval_onlyAt12(self):
        ReportNotification(hour=12, stop_hour=12, interval='hourly').save()
        self._check('hourly', datetime(2014, 10, 31, 12, 0), 1)
        self._check('hourly', datetime(2014, 10, 31, 13, 0), 0)

    def testHourlyReportWithInterval_between12And15(self):
        ReportNotification(hour=12, stop_hour=15, interval='hourly').save()
        self._check('hourly', datetime(2014, 10, 31, 11, 0), 0)
        self._check('hourly', datetime(2014, 10, 31, 12, 0), 1)
        self._check('hourly', datetime(2014, 10, 31, 13, 0), 1)
        self._check('hourly', datetime(2014, 10, 31, 14, 0), 1)
        self._check('hourly', datetime(2014, 10, 31, 15, 0), 1)
        self._check('hourly', datetime(2014, 10, 31, 16, 0), 0)

    def testHourlyReportOtherTypesDontCount(self):
        ReportNotification(hour=1, minute=0, interval='hourly').save()
        self._check('daily', datetime(2014, 10, 31, 1, 0), 0)
        self._check('weekly', datetime(2014, 10, 31, 1, 0), 0)
        self._check('monthly', datetime(2014, 10, 31, 1, 0), 0)

    def testIntervalReportDontIncludeOtherIntervals(self):
        ReportNotification(hour=1, minute=0, interval='hourly').save()
        ReportNotification(hour=1, minute=0, interval='daily').save()
        ReportNotification(hour=12, minute=0, day=4, interval='weekly').save()
        ReportNotification(hour=1, minute=0, interval='monthly').save()
        self._check('hourly', datetime(2014, 10, 1, 1, 0), 1)
        self._check('daily', datetime(2014, 10, 1, 1, 0), 1)
        self._check('weekly', datetime(2014, 10, 31, 12, 0), 1)
        self._check('monthly', datetime(2014, 10, 1, 1, 0), 1)

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


@patch('corehq.apps.reports.standard.monitoring.util.get_simplified_users',
       new=lambda q: [])
@es_test(requires=[case_adapter, form_adapter], setup_class=True)
class ScheduledReportSendingTest(TestCase):

    domain = 'test-scheduled-reports'
    REPORT_NAME_LOOKUP = {
        'worker_activity': 'corehq.apps.reports.standard.monitoring.WorkerActivityReport'
    }

    @classmethod
    def setUpClass(cls):
        super(ScheduledReportSendingTest, cls).setUpClass()

        cls.domain_obj = create_domain(cls.domain)
        cls.reports_role = UserRole.create(cls.domain, 'Test Role', permissions=HqPermissions(
            view_report_list=[cls.REPORT_NAME_LOOKUP['worker_activity']]
        ))
        cls.user = WebUser.create(
            domain=cls.domain,
            username='dummy@example.com',
            password='secret',
            created_by=None,
            created_via=None,
            role_id=cls.reports_role.get_id
        )

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
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
            domain=self.domain, hour=12, minute=None, day=30, interval='monthly', config_ids=[report_config._id],
            owner_id=self.user._id
        )
        report.save()
        report_text = get_scheduled_report_response(
            couch_user=self.user, domain=domain, scheduled_report_id=report._id
        )[0]
        self.assertTrue(self.user.username in report_text)
