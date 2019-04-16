from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import datetime

from django.test import TestCase

from corehq.apps.saved_reports.models import ScheduledReportsCheckpoint, ReportNotification
from corehq.apps.saved_reports.scheduled import create_records_for_scheduled_reports
from corehq.apps.saved_reports.tests.test_scheduled_reports import \
    delete_all_report_notifications


class ScheduledReportsCheckpointTest(TestCase):
    def tearDown(self):
        delete_all_report_notifications()
        ScheduledReportsCheckpoint.objects.all().delete()

    def test_checkpoint_created(self):
        point_1 = datetime.datetime(2019, 3, 22, 22, 46, 0, 439979)
        point_2 = datetime.datetime(2019, 3, 22, 23, 1, 38, 363898)
        self.assertEqual(len(ScheduledReportsCheckpoint.objects.all()), 0)

        create_records_for_scheduled_reports(fake_now_for_tests=point_1)
        self.assertEqual(len(ScheduledReportsCheckpoint.objects.all()), 1)
        checkpoint_1 = ScheduledReportsCheckpoint.get_latest()
        self.assertEqual(checkpoint_1.end_datetime, point_1)

        create_records_for_scheduled_reports(fake_now_for_tests=point_2)
        self.assertEqual(len(ScheduledReportsCheckpoint.objects.all()), 2)
        checkpoint_2 = ScheduledReportsCheckpoint.get_latest()
        self.assertEqual(checkpoint_2.start_datetime, point_1)
        self.assertEqual(checkpoint_2.end_datetime, point_2)

    def test_scheduled_reports_identified(self):
        point_1 = datetime.datetime(2019, 3, 22, 22, 46, 0, 439979)
        # target point in time: datetime.datetime(2019, 3, 22, 23, 0, 0, 0)
        point_2 = datetime.datetime(2019, 3, 22, 23, 11, 38, 363898)
        test_cases = [
            ('daily minute None', True, ReportNotification(hour=23, minute=None, interval='daily')),
            ('daily minute 0', True, ReportNotification(hour=23, minute=0, interval='daily')),
            ('daily minute off', False, ReportNotification(hour=23, minute=15, interval='daily')),
            ('daily hour off', False, ReportNotification(hour=22, minute=0, interval='daily')),

            ('weekly minute None', True, ReportNotification(hour=23, minute=None, day=4, interval='weekly')),
            ('weekly minute 0', True, ReportNotification(hour=23, minute=0, day=4, interval='weekly')),
            ('weekly minute off', False, ReportNotification(hour=23, minute=15, day=4, interval='weekly')),
            ('weekly hour off', False, ReportNotification(hour=22, minute=0, day=4, interval='weekly')),
            ('weekly day off', False, ReportNotification(hour=22, minute=0, day=3, interval='weekly')),

            ('monthly minute None', True, ReportNotification(hour=23, minute=None, day=22, interval='monthly')),
            ('monthly minute 0', True, ReportNotification(hour=23, minute=0, day=22, interval='monthly')),
            ('monthly minute off', False, ReportNotification(hour=23, minute=15, day=22, interval='monthly')),
            ('monthly hour off', False, ReportNotification(hour=22, minute=0, day=22, interval='monthly')),
            ('monthly day off', False, ReportNotification(hour=22, minute=0, day=20, interval='monthly')),
        ]

        create_records_for_scheduled_reports(fake_now_for_tests=point_1)

        for _, _, report in test_cases:
            report.save()

        report_ids = create_records_for_scheduled_reports(fake_now_for_tests=point_2)

        for description, should_fire, report in test_cases:
            if should_fire:
                self.assertIn(
                    report._id, report_ids,
                    "{}: should have fired but didn't".format(description))
            else:
                self.assertNotIn(
                    report._id, report_ids,
                    "{}: shouldn't have fired but did".format(description))
