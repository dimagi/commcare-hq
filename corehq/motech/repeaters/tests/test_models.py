import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from uuid import uuid4

from dateutil.parser import isoparse

from django.conf import settings
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from freezegun import freeze_time

from nose.tools import assert_in, assert_raises

from testil import eq

from corehq.motech.models import ConnectionSettings
from corehq.util.test_utils import _create_case

from ..const import (
    MAX_ATTEMPTS,
    MAX_BACKOFF_ATTEMPTS,
    MIN_RETRY_WAIT,
    RECORD_CANCELLED_STATE,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
    RECORD_SUCCESS_STATE,
    State,
)
from ..models import (
    FormRepeater,
    Repeater,
    SQLRepeatRecord,
    format_response,
    get_all_repeater_types,
    is_response,
    is_sql_id,
)

DOMAIN = 'test-domain'


def test_get_all_repeater_types():
    types = get_all_repeater_types()
    for cls in settings.REPEATER_CLASSES:
        name = cls.split('.')[-1]
        assert_in(name, types)


class RepeaterTestCase(TestCase):

    def setUp(self):
        super().setUp()
        url = 'https://www.example.com/api/'
        self.conn = ConnectionSettings.objects.create(domain=DOMAIN, name=url, url=url)
        self.repeater = FormRepeater(
            domain=DOMAIN,
            connection_settings=self.conn,
        )
        self.repeater.save()

    @classmethod
    def tearDownClass(cls):
        # TODO remove when RepeatRecords are no longer in Couch
        super().tearDownClass()
        from ..dbaccessors import delete_all_repeat_records
        delete_all_repeat_records()


class TestSoftDeleteRepeaters(RepeaterTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.all_repeaters = [self.repeater]
        for i in range(5):
            r = FormRepeater(
                domain=DOMAIN,
                connection_settings=self.conn,
            )
            r.save()
            self.all_repeaters.append(r)

    def test_soft_deletion(self):
        self.assertEqual(FormRepeater.objects.all().count(), 6)
        self.all_repeaters[1].is_deleted = True
        self.all_repeaters[1].save()
        self.all_repeaters[0].is_deleted = True
        self.all_repeaters[0].save()
        self.assertEqual(FormRepeater.objects.all().count(), 4)
        self.assertEqual(
            set(FormRepeater.objects.all().values_list('id', flat=True)),
            set([r.id for r in self.all_repeaters if not r.is_deleted])
        )

    def test_repeatrs_retired_from_sql(self):
        self.all_repeaters[0].retire()
        self.all_repeaters[4].retire()
        repeater_count = Repeater.objects.all().count()
        self.assertEqual(repeater_count, 4)


class TestRepeaterName(RepeaterTestCase):

    def test_repeater_name(self):
        self.assertEqual(self.repeater.name, self.conn.name)


class TestSQLRepeatRecordOrdering(RepeaterTestCase):

    def setUp(self):
        super().setUp()
        self.repeater.repeat_records.create(
            domain=DOMAIN,
            payload_id='eve',
            registered_at=isoparse('1970-02-01'),
        )

    def test_earlier_record_created_later(self):
        self.repeater.repeat_records.create(
            domain=self.repeater.domain,
            payload_id='lilith',
            # If Unix time starts on 1970-01-01, then I guess 1970-01-06
            # is Unix Rosh Hashanah, the sixth day of Creation, the day
            # [Lilith][1] and Adam were created from clay.
            # [1] https://en.wikipedia.org/wiki/Lilith
            registered_at=isoparse('1970-01-06'),
        )
        repeat_records = self.repeater.repeat_records.all()
        self.assertEqual(repeat_records[0].payload_id, 'lilith')
        self.assertEqual(repeat_records[1].payload_id, 'eve')

    def test_later_record_created_later(self):
        self.repeater.repeat_records.create(
            domain=self.repeater.domain,
            payload_id='cain',
            registered_at=isoparse('1995-01-06'),
        )
        repeat_records = self.repeater.repeat_records.all()
        self.assertEqual(repeat_records[0].payload_id, 'eve')
        self.assertEqual(repeat_records[1].payload_id, 'cain')


class TestConnectionSettingsSoftDelete(TestCase):

    def setUp(self):
        self.conn_1 = ConnectionSettings.objects.create(domain=DOMAIN, url='http://dummy1.com')
        self.conn_2 = ConnectionSettings.objects.create(domain=DOMAIN, url='http://dummy2.com')
        return super().setUp()

    def test_soft_delete(self):
        self.conn_1.soft_delete()
        self.assertEqual(ConnectionSettings.objects.all().count(), 1)
        self.assertEqual(ConnectionSettings.objects.all()[0].id, self.conn_2.id)


class RepeaterManagerTests(RepeaterTestCase):

    def test_all_ready_no_repeat_records(self):
        repeaters = Repeater.objects.all_ready()
        self.assertEqual(len(repeaters), 0)

    def test_all_ready_pending_repeat_record(self):
        with make_repeat_record(self.repeater, RECORD_PENDING_STATE):
            repeaters = Repeater.objects.all_ready()
            self.assertEqual(len(repeaters), 1)
            self.assertEqual(repeaters[0].id, self.repeater.id)

    def test_all_ready_failed_repeat_record(self):
        with make_repeat_record(self.repeater, RECORD_FAILURE_STATE):
            repeaters = Repeater.objects.all_ready()
            self.assertEqual(len(repeaters), 1)
            self.assertEqual(repeaters[0].id, self.repeater.id)

    def test_all_ready_succeeded_repeat_record(self):
        with make_repeat_record(self.repeater, RECORD_SUCCESS_STATE):
            repeaters = Repeater.objects.all_ready()
            self.assertEqual(len(repeaters), 0)

    def test_all_ready_cancelled_repeat_record(self):
        with make_repeat_record(self.repeater, RECORD_CANCELLED_STATE):
            repeaters = Repeater.objects.all_ready()
            self.assertEqual(len(repeaters), 0)

    def test_all_ready_paused(self):
        with make_repeat_record(self.repeater, RECORD_PENDING_STATE), \
                pause(self.repeater):
            repeaters = Repeater.objects.all_ready()
            self.assertEqual(len(repeaters), 0)

    def test_all_ready_next_future(self):
        in_five_mins = timezone.now() + timedelta(minutes=5)
        with make_repeat_record(self.repeater, RECORD_PENDING_STATE), \
                set_next_attempt_at(self.repeater, in_five_mins):
            repeaters = Repeater.objects.all_ready()
            self.assertEqual(len(repeaters), 0)

    def test_all_ready_next_past(self):
        five_mins_ago = timezone.now() - timedelta(minutes=5)
        with make_repeat_record(self.repeater, RECORD_PENDING_STATE), \
                set_next_attempt_at(self.repeater, five_mins_ago):
            repeaters = Repeater.objects.all_ready()
            self.assertEqual(len(repeaters), 1)
            self.assertEqual(repeaters[0].id, self.repeater.id)


@contextmanager
def make_repeat_record(repeater, state):
    repeat_record = repeater.repeat_records.create(
        domain=repeater.domain,
        payload_id=str(uuid4()),
        state=state,
        registered_at=timezone.now()
    )
    try:
        yield repeat_record
    finally:
        repeat_record._migration_get_couch_object().delete()


@contextmanager
def pause(repeater):
    repeater.is_paused = True
    repeater.save()
    try:
        yield
    finally:
        repeater.is_paused = False
        repeater.save()


@contextmanager
def set_next_attempt_at(repeater, when):
    repeater.next_attempt_at = when
    repeater.save()
    try:
        yield
    finally:
        repeater.next_attempt_at = None
        repeater.save()


class ResponseMock:
    pass


class IsResponseTests(SimpleTestCase):

    def test_has_text(self):
        resp = ResponseMock()
        resp.text = '<h1>Hello World</h1>'
        self.assertFalse(is_response(resp))

    def test_has_status_code(self):
        resp = ResponseMock()
        resp.status_code = 504
        self.assertFalse(is_response(resp))

    def test_has_reason(self):
        resp = ResponseMock()
        resp.reason = 'Gateway Timeout'
        self.assertFalse(is_response(resp))

    def test_has_status_code_and_reason(self):
        resp = ResponseMock()
        resp.status_code = 504
        resp.reason = 'Gateway Timeout'
        self.assertTrue(is_response(resp))


class FormatResponseTests(SimpleTestCase):

    def test_non_response(self):
        resp = ResponseMock()
        self.assertEqual(format_response(resp), '')

    def test_no_text(self):
        resp = ResponseMock()
        resp.status_code = 504
        resp.reason = 'Gateway Timeout'
        self.assertEqual(format_response(resp), '504: Gateway Timeout')

    def test_with_text(self):
        resp = ResponseMock()
        resp.status_code = 200
        resp.reason = 'OK'
        resp.text = '<h1>Hello World</h1>'
        self.assertEqual(format_response(resp), '200: OK\n'
                                                '<h1>Hello World</h1>')


class AttemptsTests(RepeaterTestCase):

    def setUp(self):
        super().setUp()
        self.just_now = timezone.now()
        self.repeater.next_attempt_at = self.just_now
        self.repeater.save()
        self.repeat_record = self.repeater.repeat_records.create(
            domain=DOMAIN,
            payload_id='eggs',
            registered_at=timezone.now(),
        )

    def test_add_success_attempt_true(self):
        self.repeat_record.add_success_attempt(response=True)
        self.assertEqual(self.repeat_record.state, RECORD_SUCCESS_STATE)
        self.assertIsNone(self.repeater.next_attempt_at)
        self.assertEqual(self.repeat_record.num_attempts, 1)
        self.assertEqual(self.repeat_record.attempts[0].state,
                         RECORD_SUCCESS_STATE)
        self.assertEqual(self.repeat_record.attempts[0].message, '')

    def test_add_success_attempt_200(self):
        resp = ResponseMock()
        resp.status_code = 200
        resp.reason = 'OK'
        resp.text = '<h1>Hello World</h1>'
        self.repeat_record.add_success_attempt(response=resp)
        self.assertEqual(self.repeat_record.state, RECORD_SUCCESS_STATE)
        self.assertIsNone(self.repeater.next_attempt_at)
        self.assertEqual(self.repeat_record.num_attempts, 1)
        self.assertEqual(self.repeat_record.attempts[0].state,
                         RECORD_SUCCESS_STATE)
        self.assertEqual(self.repeat_record.attempts[0].message,
                         format_response(resp))

    def test_add_server_failure_attempt_fail(self):
        message = '504: Gateway Timeout'
        self.repeat_record.add_server_failure_attempt(message=message)
        self.assertEqual(self.repeat_record.state, RECORD_FAILURE_STATE)
        self.assertGreater(self.repeater.last_attempt_at, self.just_now)
        self.assertEqual(self.repeater.next_attempt_at,
                         self.repeater.last_attempt_at + MIN_RETRY_WAIT)
        self.assertEqual(self.repeat_record.num_attempts, 1)
        self.assertEqual(self.repeat_record.attempts[0].state,
                         RECORD_FAILURE_STATE)
        self.assertEqual(self.repeat_record.attempts[0].message, message)
        self.assertEqual(self.repeat_record.attempts[0].traceback, '')

    def test_add_server_failure_attempt_cancel(self):
        message = '504: Gateway Timeout'
        while self.repeat_record.state != RECORD_CANCELLED_STATE:
            self.repeat_record.add_server_failure_attempt(message=message)

        self.assertGreater(self.repeater.last_attempt_at, self.just_now)
        # Interval is MIN_RETRY_WAIT because attempts were very close together
        self.assertEqual(self.repeater.next_attempt_at,
                         self.repeater.last_attempt_at + MIN_RETRY_WAIT)
        self.assertEqual(self.repeat_record.num_attempts,
                         MAX_BACKOFF_ATTEMPTS + 1)
        attempts = list(self.repeat_record.attempts)
        expected_states = ([RECORD_FAILURE_STATE] * MAX_BACKOFF_ATTEMPTS
                           + [RECORD_CANCELLED_STATE])
        self.assertEqual([a.state for a in attempts], expected_states)
        self.assertEqual(attempts[-1].message, message)
        self.assertEqual(attempts[-1].traceback, '')

    def test_add_client_failure_attempt_fail(self):
        message = '409: Conflict'
        self.repeat_record.add_client_failure_attempt(message=message)
        self.assertEqual(self.repeat_record.state, RECORD_FAILURE_STATE)
        self.assertIsNone(self.repeater.last_attempt_at)
        self.assertIsNone(self.repeater.next_attempt_at)
        self.assertEqual(self.repeat_record.num_attempts, 1)
        self.assertEqual(self.repeat_record.attempts[0].state,
                         RECORD_FAILURE_STATE)
        self.assertEqual(self.repeat_record.attempts[0].message, message)
        self.assertEqual(self.repeat_record.attempts[0].traceback, '')

    def test_add_client_failure_attempt_cancel(self):
        message = '409: Conflict'
        while self.repeat_record.state != RECORD_CANCELLED_STATE:
            self.repeat_record.add_client_failure_attempt(message=message)
        self.assertIsNone(self.repeater.last_attempt_at)
        self.assertIsNone(self.repeater.next_attempt_at)
        self.assertEqual(self.repeat_record.num_attempts,
                         MAX_ATTEMPTS + 1)
        attempts = list(self.repeat_record.attempts)
        expected_states = ([RECORD_FAILURE_STATE] * MAX_ATTEMPTS
                           + [RECORD_CANCELLED_STATE])
        self.assertEqual([a.state for a in attempts], expected_states)
        self.assertEqual(attempts[-1].message, message)
        self.assertEqual(attempts[-1].traceback, '')

    def test_add_client_failure_attempt_no_retry(self):
        message = '422: Unprocessable Entity'
        while self.repeat_record.state != RECORD_CANCELLED_STATE:
            self.repeat_record.add_client_failure_attempt(message=message, retry=False)
        self.assertIsNone(self.repeater.last_attempt_at)
        self.assertIsNone(self.repeater.next_attempt_at)
        self.assertEqual(self.repeat_record.num_attempts, 1)
        self.assertEqual(self.repeat_record.attempts[0].state, RECORD_CANCELLED_STATE)
        self.assertEqual(self.repeat_record.attempts[0].message, message)
        self.assertEqual(self.repeat_record.attempts[0].traceback, '')

    def test_add_payload_exception_attempt(self):
        message = 'ValueError: Schema validation failed'
        tb_str = 'Traceback ...'
        self.repeat_record.add_payload_exception_attempt(message=message,
                                                         tb_str=tb_str)
        self.assertEqual(self.repeat_record.state, RECORD_CANCELLED_STATE)
        # Note: Our payload issues do not affect how we deal with their
        #       server issues:
        self.assertEqual(self.repeater.next_attempt_at, self.just_now)
        self.assertEqual(self.repeat_record.num_attempts, 1)
        self.assertEqual(self.repeat_record.attempts[0].state,
                         RECORD_CANCELLED_STATE)
        self.assertEqual(self.repeat_record.attempts[0].message, message)
        self.assertEqual(self.repeat_record.attempts[0].traceback, tb_str)

    def test_cached_attempts(self):
        def clear_attempts_cache():
            # can be removed with RepeatRecord (Couch model)
            # the cache is populated when the couch record is saved
            self.repeat_record.attempts._result_cache = None

        self.repeat_record.add_client_failure_attempt(message="Fail")
        clear_attempts_cache()

        with self.assertNumQueries(1):
            self.assertEqual(len(self.repeat_record.attempts), 1)
        with self.assertNumQueries(0):
            self.assertEqual(len(self.repeat_record.attempts), 1)

        self.repeat_record.add_client_failure_attempt(message="Fail")
        clear_attempts_cache()

        with self.assertNumQueries(1):
            self.assertEqual(len(self.repeat_record.attempts), 2)
        with self.assertNumQueries(0):
            self.assertEqual(len(self.repeat_record.attempts), 2)


class TestConnectionSettingsUsedBy(TestCase):

    def setUp(self):
        super().setUp()
        url = 'https://www.example.com/api/'
        self.conn = ConnectionSettings.objects.create(domain=DOMAIN, name=url, url=url)
        self.repeater = FormRepeater(
            domain=DOMAIN,
            connection_settings_id=self.conn.id
        )
        self.repeater.save()

    def test_connection_settings_used_by(self):
        self.assertEqual(self.conn.used_by, {'Data Forwarding'})

    def test_conn_with_no_used_by(self):
        new_conn = ConnectionSettings.objects.create(
            url='http://blah-url.com',
            domain='nice-domain'
        )
        self.assertEqual(new_conn.used_by, set())

    def tearDown(self):
        self.repeater.delete()
        super().tearDown()


class TestRepeaterConnectionSettings(RepeaterTestCase):

    def test_connection_settings_are_accessible(self):
        self.assertEqual(self.repeater.connection_settings.url, 'https://www.example.com/api/')

    def test_used_connection_setting_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.repeater.connection_settings.delete()
        with self.assertRaises(ProtectedError):
            ConnectionSettings.objects.filter(id=self.conn.id).delete()
        with self.assertRaises(ProtectedError):
            ConnectionSettings.all_objects.filter(id=self.conn.id).delete()


def test_attempt_forward_now_kwargs():
    rr = SQLRepeatRecord()
    with assert_raises(TypeError):
        rr.attempt_forward_now(True)


@patch("corehq.motech.repeaters.tasks.retry_process_repeat_record")
@patch("corehq.motech.repeaters.tasks.process_repeat_record")
class TestAttemptForwardNow(RepeaterTestCase):
    before_now = datetime.utcnow() - timedelta(seconds=1)

    def test_future_next_check(self, process, retry_process):
        rec = self.new_record(next_check=datetime.utcnow() + timedelta(hours=1))
        rec.attempt_forward_now()

        self.assert_not_called(process, retry_process)

    def test_success_state(self, process, retry_process):
        rec = self.new_record(state=RECORD_SUCCESS_STATE, next_check=None)
        rec.attempt_forward_now()

        self.assert_not_called(process, retry_process)

    def test_cancelled_state(self, process, retry_process):
        rec = self.new_record(state=RECORD_CANCELLED_STATE, next_check=None)
        rec.attempt_forward_now()

        self.assert_not_called(process, retry_process)

    def test_delayed_task(self, process, retry_process):
        rec = self.new_record()
        rec.attempt_forward_now()

        process.delay.assert_called_once()
        self.assert_not_called(retry_process)

    def test_fire_synchronously(self, process, retry_process):
        rec = self.new_record()
        rec.attempt_forward_now(fire_synchronously=True)

        process.assert_called_once()
        self.assert_not_called(retry_process)

    def test_retry(self, process, retry_process):
        rec = self.new_record()
        rec.attempt_forward_now(is_retry=True)

        retry_process.delay.assert_called_once()
        self.assert_not_called(process)

    def test_optimistic_lock(self, process, retry_process):
        rec = self.new_record()

        two = SQLRepeatRecord.objects.get(id=rec.id)
        two.next_check = datetime.utcnow() - timedelta(days=1)
        two.save()

        rec.attempt_forward_now()

        self.assert_not_called(process, retry_process)

    def assert_not_called(self, *tasks):
        for task in tasks:
            try:
                task.assert_not_called()
                task.delay.assert_not_called()
            except AssertionError as err:
                raise AssertionError(f"{task} unexpectedly called:\n{err}")

    def new_record(self, next_check=before_now, state=RECORD_PENDING_STATE):
        rec = SQLRepeatRecord(
            domain="test",
            repeater_id=self.repeater.repeater_id,
            payload_id="c0ffee",
            registered_at=self.before_now,
            next_check=next_check,
            state=state,
        )
        rec.save()
        return rec


class TestRepeaterModelMethods(RepeaterTestCase):

    def test_register(self):
        case_id = uuid.uuid4().hex
        payload, cases = _create_case(
            domain=DOMAIN, case_id=case_id, case_type='some_case', owner_id='abcd'
        )
        repeat_record = self.repeater.register(payload, fire_synchronously=True)
        self.addCleanup(repeat_record._migration_get_couch_object().delete)
        self.assertEqual(repeat_record.payload_id, payload.get_id)
        all_records = list(SQLRepeatRecord.objects.iterate(DOMAIN))
        self.assertEqual(len(all_records), 1)
        self.assertEqual(all_records[0].id, repeat_record.id)

    def test_send_request(self):
        case_id = uuid.uuid4().hex
        payload, cases = _create_case(
            domain=DOMAIN, case_id=case_id, case_type='some_case', owner_id='abcd'
        )
        repeat_record = self.repeater.register(payload, fire_synchronously=True)
        self.addCleanup(repeat_record._migration_get_couch_object().delete)
        from corehq.motech.repeaters.tests.test_models_slow import ResponseMock
        resp = ResponseMock(status_code=200, reason='OK')
        # Basic test checks if send_request is called
        with patch('corehq.motech.repeaters.models.simple_request') as simple_request:
            simple_request.return_value = resp
            self.repeater.send_request(repeat_record, payload)

        self.assertTrue(simple_request.called)


class TestFormRepeaterAllowedToForward(RepeaterTestCase):

    def test_white_list_empty(self):
        self.repeater.white_listed_form_xmlns = []
        payload = Mock(xmlns='http://openrosa.org/formdesigner/abc123')
        self.assertTrue(self.repeater.allowed_to_forward(payload))

    def test_payload_white_listed(self):
        self.repeater.white_listed_form_xmlns = [
            'http://openrosa.org/formdesigner/abc123'
        ]
        payload = Mock(xmlns='http://openrosa.org/formdesigner/abc123')
        self.assertTrue(self.repeater.allowed_to_forward(payload))

    def test_payload_not_white_listed(self):
        self.repeater.white_listed_form_xmlns = [
            'http://openrosa.org/formdesigner/abc123'
        ]
        payload = Mock(xmlns='http://openrosa.org/formdesigner/def456')
        self.assertFalse(self.repeater.allowed_to_forward(payload))


class TestRepeatRecordManager(RepeaterTestCase):
    before_now = datetime.utcnow() - timedelta(days=1)

    def test_count_pending_records_for_domain(self):
        now = datetime.utcnow()
        self.new_record(next_check=now - timedelta(hours=2))
        self.new_record(next_check=now - timedelta(hours=1))
        self.new_record(next_check=now - timedelta(minutes=15))
        self.new_record(next_check=now - timedelta(minutes=5))
        self.new_record(next_check=None, state=State.Success)
        self.new_record(next_check=now - timedelta(hours=1), domain="other")
        pending = SQLRepeatRecord.objects.count_pending_records_for_domain("test")
        self.assertEqual(pending, 4)

    def test_count_overdue(self):
        now = datetime.utcnow()
        self.new_record(next_check=now - timedelta(hours=2))
        self.new_record(next_check=now - timedelta(hours=1))
        self.new_record(next_check=now - timedelta(minutes=15))
        self.new_record(next_check=now - timedelta(minutes=5))
        self.new_record(next_check=None, state=State.Success)
        overdue = SQLRepeatRecord.objects.count_overdue()
        self.assertEqual(overdue, 3)

    iter_partition = SQLRepeatRecord.objects.iter_partition

    def test_one_partition(self):
        iter_partition = type(self).iter_partition
        all_ids = self.make_records(5)
        start = datetime.utcnow()
        ids = {r.id for r in iter_partition(start, 0, 1)}
        self.assertEqual(ids, all_ids)

    def test_four_partitions(self):
        iter_partition = type(self).iter_partition
        all_ids = self.make_records(16)
        start = datetime.utcnow()
        ids0 = {r.id for r in iter_partition(start, 0, 4)}
        ids1 = {r.id for r in iter_partition(start, 1, 4)}
        ids2 = {r.id for r in iter_partition(start, 2, 4)}
        ids3 = {r.id for r in iter_partition(start, 3, 4)}

        self.assertEqual(ids0 | ids1 | ids2 | ids3, all_ids)

        self.assertTrue(ids0)
        self.assertTrue(ids1)
        self.assertTrue(ids2)
        self.assertTrue(ids3)

        self.assertFalse(ids0 & ids1)
        self.assertFalse(ids0 & ids2)
        self.assertFalse(ids0 & ids3)

        self.assertFalse(ids1 & ids0)
        self.assertFalse(ids1 & ids2)
        self.assertFalse(ids1 & ids3)

        self.assertFalse(ids2 & ids0)
        self.assertFalse(ids2 & ids1)
        self.assertFalse(ids2 & ids3)

        self.assertFalse(ids3 & ids0)
        self.assertFalse(ids3 & ids1)
        self.assertFalse(ids3 & ids2)

    def test_partition_start(self):
        iter_partition = type(self).iter_partition
        all_ids = self.make_records(5)
        self.new_record(next_check=datetime.utcnow() + timedelta(hours=1))
        start = datetime.utcnow()
        ids = {r.id for r in iter_partition(start, 0, 1)}
        self.assertEqual(ids, all_ids)

    def test_get_domains_with_records(self):
        self.new_record(domain='a')
        self.new_record(domain='b')
        self.new_record(domain='c')
        self.assertEqual(
            set(SQLRepeatRecord.objects.get_domains_with_records()),
            {'a', 'b', 'c'},
        )

    def test_get_domains_with_records_with_filter(self):
        self.new_record(domain='alex')
        self.new_record(domain='alice')
        self.new_record(domain='carl')
        self.assertEqual(
            set(SQLRepeatRecord.objects.get_domains_with_records().filter(domain__startswith="al")),
            {'alex', 'alice'},
        )

    def new_record(self, next_check=before_now, state=State.Pending, domain="test"):
        return SQLRepeatRecord.objects.create(
            domain=domain,
            repeater_id=self.repeater.repeater_id,
            payload_id="c0ffee",
            registered_at=self.before_now,
            next_check=next_check,
            state=state,
        )

    def make_records(self, n):
        now = timezone.now() - timedelta(seconds=10)
        records = SQLRepeatRecord.objects.bulk_create(SQLRepeatRecord(
            domain="test",
            repeater=self.repeater,
            payload_id="c0ffee",
            registered_at=now,
            next_check=now,
        ) for i in range(n))
        return {r.id for r in records}

    def tearDown(self):
        from ..dbaccessors import delete_all_repeat_records
        delete_all_repeat_records()


class TestRepeatRecordMethods(TestCase):

    def test_repeater_returns_active_repeater(self):
        repeater = Repeater.objects.create(
            domain=self.domain,
            connection_settings=self.conn_settings,
            is_deleted=False
        )
        repeat_record = SQLRepeatRecord.objects.create(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=repeater.repeater_id
        )
        self.addCleanup(repeat_record._migration_get_couch_object().delete)

        self.assertIsNotNone(repeat_record.repeater)

    def test_repeater_returns_deleted_repeater(self):
        repeater = Repeater.objects.create(
            domain=self.domain,
            connection_settings=self.conn_settings,
            is_deleted=True
        )
        repeat_record = SQLRepeatRecord.objects.create(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=repeater.repeater_id
        )
        self.addCleanup(repeat_record._migration_get_couch_object().delete)

        self.assertTrue(repeat_record.repeater.is_deleted)

    def test_repeater_raises_if_not_found(self):
        repeat_record = SQLRepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id='404aaaaaaaaaaaaaaaaaaaaaaaaaa404',
        )

        with self.assertRaises(Repeater.DoesNotExist):
            repeat_record.repeater

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'repeat-record-tests'
        cls.conn_settings = ConnectionSettings.objects.create(
            domain=cls.domain,
            name='To Be Deleted',
            url="http://localhost/api/"
        )
        cls.repeater = Repeater.objects.create(
            domain=cls.domain,
            connection_settings=cls.conn_settings,
        )

    def test_requeue(self):
        now = datetime.utcnow()
        record = SQLRepeatRecord(
            domain="test",
            repeater_id=self.repeater.id.hex,
            payload_id="abc123",
            state=State.Empty,
            registered_at=now - timedelta(hours=1),
        )
        record.requeue()

        self.assertEqual(record.state, State.Pending)
        self.assertLessEqual(record.next_check, datetime.utcnow())

    def test_get_payload(self):
        record = SQLRepeatRecord(
            domain="test",
            repeater_id=self.repeater.id.hex,
            payload_id="abc123",
        )
        with patch.object(Repeater, "get_payload") as mock:
            record.get_payload()
        mock.assert_called_once_with(record)

    def test_postpone_by(self):
        now = datetime.utcnow()
        hour = timedelta(hours=1)
        record = SQLRepeatRecord(
            domain="test",
            repeater_id=self.repeater.id.hex,
            payload_id="abc123",
            registered_at=now - hour,
        )
        with freeze_time(now):
            record.postpone_by(3 * hour)
        self.assertEqual(record.next_check, now + 3 * hour)


class TestRepeatRecordMethodsNoDB(SimpleTestCase):
    domain = 'repeat-record-tests'

    def test_exceeded_max_retries_returns_false_if_fewer_tries_than_possible(self):
        repeat_record = SQLRepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            state=State.Fail
        )

        with patch.object(SQLRepeatRecord, "num_attempts", 0), \
                patch.object(repeat_record, "max_possible_tries", 1):
            self.assertFalse(repeat_record.exceeded_max_retries)

    def test_exceeded_max_retries_returns_true_if_equal(self):
        repeat_record = SQLRepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            state=State.Fail
        )

        with patch.object(SQLRepeatRecord, "num_attempts", 1), \
                patch.object(repeat_record, "max_possible_tries", 1):
            self.assertTrue(repeat_record.exceeded_max_retries)

    def test_exceeded_max_retries_returns_true_if_more_tries_than_possible(self):
        repeat_record = SQLRepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            state=State.Fail
        )

        with patch.object(SQLRepeatRecord, "num_attempts", 2), \
                patch.object(repeat_record, "max_possible_tries", 1):
            self.assertTrue(repeat_record.exceeded_max_retries)

    def test_exceeded_max_retries_returns_false_if_not_failure_state(
            self):
        repeat_record = SQLRepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            state=State.Success,
        )

        with patch.object(SQLRepeatRecord, "num_attempts", 2), \
                patch.object(repeat_record, "max_possible_tries", 1):
            self.assertFalse(repeat_record.exceeded_max_retries)


def test_is_sql_id():
    def test(value, expect):
        eq(is_sql_id(value), expect, f"value was: {value!r}")

    yield test, 1234, True
    yield test, '1234', True
    yield test, 'b6859ae05fd94dccbc3dfd25cdc6cb2c', False
    yield test, 'b6859ae0-5fd9-4dcc-bc3d-fd25cdc6cb2c', False

    # numeric str is considered UUID if number of digits is 32
    yield test, '40400000000000000000000000000404', False
    yield test, '40400000-0000-0000-0000-000000000404', False
