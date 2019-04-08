from __future__ import absolute_import
from __future__ import print_function
import datetime

import mock
from django.test import TestCase

from corehq.apps.saved_reports.models import ScheduledReportsCheckpoint, ReportNotification, \
    ScheduledReportRecord
from corehq.apps.saved_reports.scheduled import create_records_for_scheduled_reports
from corehq.apps.saved_reports.tasks import queue_scheduled_reports, send_report
from corehq.apps.saved_reports.tests.test_scheduled_reports import \
    delete_all_report_notifications


class ScheduledReportsCheckpointTest(TestCase):
    def tearDown(self):
        delete_all_report_notifications()
        ScheduledReportsCheckpoint.objects.all().delete()
        ScheduledReportRecord.objects.all().delete()

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
        records = {record.scheduled_report_id: record for record in ScheduledReportRecord.objects
                   .filter(state=ScheduledReportRecord.States.queued).all()}

        for description, should_fire, report in test_cases:
            if should_fire:
                self.assertIn(
                    report._id, report_ids,
                    "{}: should have fired but didn't".format(description))
                self.assertIn(
                    report._id, records,
                    "{}: should be queued but isn't".format(description))
            else:
                self.assertNotIn(
                    report._id, report_ids,
                    "{}: shouldn't have fired but did".format(description))
                self.assertNotIn(
                    report._id, records,
                    "{}: shouldn't be queued but is".format(description))

    def test_scheduled_reports_skipped(self):
        point_1 = datetime.datetime(2019, 3, 22, 22, 46, 0, 439979)
        # target points in time:
        #   datetime.datetime(2019, 3, 22, 23, 0, 0, 0)
        #   datetime.datetime(2019, 3, 23, 23, 0, 0, 0)
        point_2 = datetime.datetime(2019, 3, 23, 23, 11, 38, 363898)
        test_cases = [
            ('daily double', (1, 1), ReportNotification(hour=23, minute=0, interval='daily')),
            ('daily single', (0, 1), ReportNotification(hour=0, minute=0, interval='daily')),
            ('weekly single', (0, 1), ReportNotification(hour=23, minute=0, day=4, interval='weekly')),
        ]

        create_records_for_scheduled_reports(fake_now_for_tests=point_1)

        for _, _, report in test_cases:
            report.save()

        report_ids = create_records_for_scheduled_reports(fake_now_for_tests=point_2)
        records_queued = (ScheduledReportRecord.objects
                          .filter(state=ScheduledReportRecord.States.queued).all())
        records_skipped = (ScheduledReportRecord.objects
                           .filter(state=ScheduledReportRecord.States.skipped).all())
        print(records_queued, records_skipped)
        for description, (n_skipped, n_queued), report in test_cases:
            skipped = [record for record in records_skipped if record.scheduled_report_id == report._id]
            queued = [record for record in records_queued if record.scheduled_report_id == report._id]

            self.assertEqual(len(skipped), n_skipped, "{}: {} != {}".format(description, len(skipped), n_skipped))
            self.assertEqual(len(queued), n_queued, "{}: {} != {}".format(description, len(queued), n_queued))

            if n_queued:
                self.assertIn(
                    report._id, report_ids,
                    "{}: should have fired but didn't".format(description))
            else:
                self.assertNotIn(
                    report._id, report_ids,
                    "{}: shouldn't have fired but did".format(description))

    def test_queue_scheduled_reports(self):
        report = ReportNotification(hour=23, minute=0, interval='daily')
        report.save()
        unfired_report = ReportNotification(hour=24, minute=0, interval='daily')
        unfired_report.save()
        checkpoint = ScheduledReportsCheckpoint.objects.create(
            start_datetime=datetime.datetime(2019, 3, 22, 22, 46, 0, 439979),
            end_datetime=datetime.datetime(2019, 3, 22, 23, 11, 0, 123011),
        )
        ScheduledReportRecord.objects.create(
            scheduled_report_id=report._id,
            state=ScheduledReportRecord.States.queued,
            from_checkpoint=checkpoint,
            scheduled_for=datetime.datetime(2019, 3, 22, 23, 0, 0, 0)
        )

        sent = []

        def fake_send(self):
            sent.append(self._id)

        with mock.patch('corehq.apps.saved_reports.models.ReportNotification.send', fake_send):
            queue_scheduled_reports(send_report_override_for_tests=send_report)

        succeeded_records = (
            ScheduledReportRecord.objects.filter(state=ScheduledReportRecord.States.succeeded)
            .values_list('scheduled_report_id', flat=True)
        )
        self.assertIn(report._id, sent)
        self.assertNotIn(unfired_report._id, sent)
        self.assertIn(report._id, succeeded_records)
        self.assertNotIn(unfired_report._id, succeeded_records)
