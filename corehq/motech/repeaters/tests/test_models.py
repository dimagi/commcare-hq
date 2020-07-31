from datetime import datetime, timedelta

from django.test import SimpleTestCase, TestCase

from corehq.motech.repeaters.models import (
    FormRepeater,
    RepeatRecord,
    RepeatRecordAttempt,
)

DOMAIN = 'doh-maine'


class IsConnectionWorkingTests(SimpleTestCase):
    def test_new_repeater(self):
        rep = FormRepeater(
            domain=DOMAIN,
            url='https://server.example.com/api/',
        )
        a_moment_ago = datetime.utcnow() - rep.started_at
        self.assertLess(a_moment_ago, timedelta(milliseconds=1))
        self.assertIsNone(rep.last_success_at)
        self.assertEqual(rep.failure_streak, 0)
        self.assertTrue(rep.is_connection_working())

    def test_newish_repeater_no_records(self):
        two_months = timedelta(days=60)
        rep = FormRepeater(
            domain=DOMAIN,
            url='https://server.example.com/api/',
            started_at=datetime.utcnow() - two_months,
        )
        self.assertTrue(rep.is_connection_working())

    def test_newish_repeater_only_failed_records(self):
        two_months = timedelta(days=60)
        rep = FormRepeater(
            domain=DOMAIN,
            url='https://server.example.com/api/',
            started_at=datetime.utcnow() - two_months,
            failure_streak=10_000,
        )
        self.assertTrue(rep.is_connection_working())

    def test_newish_repeater_too_many_failed_records(self):
        two_months = timedelta(days=60)
        rep = FormRepeater(
            domain=DOMAIN,
            url='https://server.example.com/api/',
            started_at=datetime.utcnow() - two_months,
            failure_streak=10_001,
        )
        self.assertFalse(rep.is_connection_working())

    def test_old_repeater_no_records(self):
        four_months = timedelta(days=120)
        rep = FormRepeater(
            domain=DOMAIN,
            url='https://server.example.com/api/',
            started_at=datetime.utcnow() - four_months,
        )
        self.assertTrue(rep.is_connection_working())

    def test_old_repeater_only_failed_records(self):
        four_months = timedelta(days=120)
        rep = FormRepeater(
            domain=DOMAIN,
            url='https://server.example.com/api/',
            started_at=datetime.utcnow() - four_months,
            failure_streak=1,
        )
        self.assertFalse(rep.is_connection_working())

    def test_old_repeater_recent_success(self):
        two_months = timedelta(days=60)
        four_months = timedelta(days=120)
        rep = FormRepeater(
            domain=DOMAIN,
            url='https://server.example.com/api/',
            started_at=datetime.utcnow() - four_months,
            failure_streak=10_000,
            last_success_at=datetime.utcnow() - two_months,
        )
        self.assertTrue(rep.is_connection_working())


class TestRepeatRecordsUpdateRepeater(TestCase):
    def setUp(self):
        self.rep = FormRepeater(
            domain=DOMAIN,
            url='https://server.example.com/api/',
        )
        self.rep.save()

    def tearDown(self):
        self.rep.delete()

    def test_success(self):
        one_minute = timedelta(minutes=1)
        rec = RepeatRecord(
            domain=DOMAIN,
            repeater_id=self.rep.get_id,
        )
        attempt = RepeatRecordAttempt(
            datetime=datetime.utcnow() - one_minute,
            success_response='w00t',
            succeeded=True,
        )
        rec.add_attempt(attempt)

        self.assertEqual(rec.repeater.last_success_at, attempt.datetime)
        self.assertEqual(rec.repeater.failure_streak, 0)

    def test_failure(self):
        one_minute = timedelta(minutes=1)
        rec = RepeatRecord(
            domain=DOMAIN,
            repeater_id=self.rep.get_id,
        )
        attempt = RepeatRecordAttempt(
            datetime=datetime.utcnow() - one_minute,
            failure_reason='oops',
            succeeded=False,
        )
        rec.add_attempt(attempt)

        self.assertIsNone(rec.repeater.last_success_at)
        self.assertEqual(rec.repeater.failure_streak, 1)
