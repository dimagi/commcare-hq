import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta
from http import HTTPStatus
from unittest.mock import Mock, patch
from uuid import uuid4

from django.conf import settings
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

import pytest
from dateutil.parser import isoparse
from time_machine import travel
from unmagic import fixture, use

from corehq.motech.models import ConnectionSettings
from corehq.motech.repeater_helpers import RepeaterResponse
from corehq.util.test_utils import _create_case, flag_enabled

from ..const import (
    COMMCARE_CONNECT_URL,
    MAX_ATTEMPTS,
    MAX_BACKOFF_ATTEMPTS,
    RECORD_QUEUED_STATES,
    State,
)
from ..models import (
    HTTP_STATUS_BACK_OFF,
    DataSourceUpdate,
    FormRepeater,
    Repeater,
    RepeatRecord,
    format_response,
    forwards_to_commcare_connect,
    get_all_repeater_types,
    is_response,
    is_success_response,
)

DOMAIN = 'test-domain'


def test_get_all_repeater_types():
    types = get_all_repeater_types()
    for cls in settings.REPEATER_CLASSES:
        name = cls.split('.')[-1]
        assert name in types


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
        assert FormRepeater.objects.all().count() == 6
        self.all_repeaters[1].is_deleted = True
        self.all_repeaters[1].save()
        self.all_repeaters[0].is_deleted = True
        self.all_repeaters[0].save()
        assert FormRepeater.objects.all().count() == 4
        assert (
            set(FormRepeater.objects.all().values_list('id', flat=True))
            == set([r.id for r in self.all_repeaters if not r.is_deleted])
        )

    def test_repeatrs_retired_from_sql(self):
        self.all_repeaters[0].retire()
        self.all_repeaters[4].retire()
        repeater_count = Repeater.objects.all().count()
        assert repeater_count == 4


class TestRepeaterName(RepeaterTestCase):

    def test_repeater_name(self):
        assert self.repeater.name == self.conn.name


class TestRepeatRecordOrdering(RepeaterTestCase):

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
        assert repeat_records[0].payload_id == 'lilith'
        assert repeat_records[1].payload_id == 'eve'

    def test_later_record_created_later(self):
        self.repeater.repeat_records.create(
            domain=self.repeater.domain,
            payload_id='cain',
            registered_at=isoparse('1995-01-06'),
        )
        repeat_records = self.repeater.repeat_records.all()
        assert repeat_records[0].payload_id == 'eve'
        assert repeat_records[1].payload_id == 'cain'


class TestConnectionSettingsSoftDelete(TestCase):

    def setUp(self):
        self.conn_1 = ConnectionSettings.objects.create(domain=DOMAIN, url='http://dummy1.com')
        self.conn_2 = ConnectionSettings.objects.create(domain=DOMAIN, url='http://dummy2.com')
        return super().setUp()

    def test_soft_delete(self):
        self.conn_1.soft_delete()
        assert ConnectionSettings.objects.all().count() == 1
        assert ConnectionSettings.objects.all()[0].id == self.conn_2.id


class RepeaterManagerTests(RepeaterTestCase):

    def test_all_ready_no_repeat_records(self):
        repeater_ids = Repeater.objects.get_all_ready_ids_by_domain()
        assert len(repeater_ids) == 0

    def test_all_ready_pending_repeat_record(self):
        with make_repeat_record(self.repeater, State.Pending):
            repeater_ids = Repeater.objects.get_all_ready_ids_by_domain()
            assert (
                dict(repeater_ids)
                == {self.repeater.domain: [self.repeater.repeater_id]}
            )

    def test_all_ready_failed_repeat_record(self):
        with make_repeat_record(self.repeater, State.Fail):
            repeater_ids = Repeater.objects.get_all_ready_ids_by_domain()
            assert (
                dict(repeater_ids)
                == {self.repeater.domain: [self.repeater.repeater_id]}
            )

    def test_all_ready_succeeded_repeat_record(self):
        with make_repeat_record(self.repeater, State.Success):
            repeater_ids = Repeater.objects.get_all_ready_ids_by_domain()
            assert len(repeater_ids) == 0

    def test_all_ready_cancelled_repeat_record(self):
        with make_repeat_record(self.repeater, State.Cancelled):
            repeater_ids = Repeater.objects.get_all_ready_ids_by_domain()
            assert len(repeater_ids) == 0

    def test_all_ready_paused(self):
        with (
            make_repeat_record(self.repeater, State.Pending),
            pause(self.repeater)
        ):
            repeater_ids = Repeater.objects.get_all_ready_ids_by_domain()
            assert len(repeater_ids) == 0

    def test_all_ready_next_future(self):
        in_five_mins = timezone.now() + timedelta(minutes=5)
        with (
            make_repeat_record(self.repeater, State.Pending),
            set_next_attempt_at(self.repeater, in_five_mins)
        ):
            repeater_ids = Repeater.objects.get_all_ready_ids_by_domain()
            assert len(repeater_ids) == 0

    def test_all_ready_next_past(self):
        five_mins_ago = timezone.now() - timedelta(minutes=5)
        with (
            make_repeat_record(self.repeater, State.Pending),
            set_next_attempt_at(self.repeater, five_mins_ago)
        ):
            repeater_ids = Repeater.objects.get_all_ready_ids_by_domain()
            assert (
                dict(repeater_ids)
                == {self.repeater.domain: [self.repeater.repeater_id]}
            )

    def test_all_ready_ids(self):
        with make_repeat_record(self.repeater, State.Pending):
            repeater_ids = Repeater.objects.get_all_ready_ids_by_domain()
            assert (
                dict(repeater_ids)
                == {self.repeater.domain: [self.repeater.repeater_id]}
            )

    def test_distinct(self):
        with (
            make_repeat_record(self.repeater, State.Pending),
            make_repeat_record(self.repeater, State.Pending),
            make_repeat_record(self.repeater, State.Pending),
        ):
            repeater_ids = Repeater.objects.get_all_ready_ids_by_domain()
            assert (
                dict(repeater_ids)
                == {self.repeater.domain: [self.repeater.repeater_id]}
            )


@contextmanager
def make_repeat_record(repeater, state):
    yield repeater.repeat_records.create(
        domain=repeater.domain,
        payload_id=str(uuid4()),
        state=state,
        registered_at=timezone.now()
    )


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


class Unknown:
    pass


class IsResponseTests(SimpleTestCase):

    def test_has_text(self):
        resp = Unknown()
        resp.text = '<h1>Hello World</h1>'
        assert not is_response(resp)

    def test_has_status_code(self):
        resp = Unknown()
        resp.status_code = 504
        assert not is_response(resp)

    def test_has_reason(self):
        resp = Unknown()
        resp.reason = 'Gateway Timeout'
        assert not is_response(resp)

    def test_has_status_code_and_reason(self):
        resp = Unknown()
        resp.status_code = 504
        resp.reason = 'Gateway Timeout'
        assert is_response(resp)


class ResponseMock:
    status_code = 0
    reason = ''
    text = ''
    url = ''


class FormatResponseTests(SimpleTestCase):

    def test_non_response(self):
        resp = Unknown()
        assert format_response(resp) == ''

    def test_no_text(self):
        resp = ResponseMock()
        resp.status_code = 504
        resp.reason = 'Gateway Timeout'
        assert format_response(resp) == '504: Gateway Timeout'

    def test_with_text(self):
        resp = ResponseMock()
        resp.status_code = 200
        resp.reason = 'OK'
        resp.text = '<h1>Hello World</h1>'
        assert format_response(resp) == '200: OK\n<h1>Hello World</h1>'

    def test_with_url(self):
        resp = ResponseMock()
        resp.status_code = 200
        resp.reason = 'OK'
        resp.text = '<h1>Hello World</h1>'
        resp.url = 'https://test.com'
        assert format_response(resp) == 'https://test.com\n200: OK\n<h1>Hello World</h1>'


class AttemptsTests(RepeaterTestCase):

    def setUp(self):
        super().setUp()
        self.repeat_record = self.repeater.repeat_records.create(
            domain=DOMAIN,
            payload_id='eggs',
            registered_at=timezone.now(),
        )

    def test_add_success_attempt_true(self):
        self.repeat_record.add_success_attempt(response=True)
        assert self.repeat_record.state == State.Success
        assert self.repeat_record.num_attempts == 1
        assert self.repeat_record.attempts[0].state == State.Success
        assert self.repeat_record.attempts[0].message == ''

    def test_add_success_attempt_200(self):
        resp = ResponseMock()
        resp.status_code = 200
        resp.reason = 'OK'
        resp.text = '<h1>Hello World</h1>'
        self.repeat_record.add_success_attempt(response=resp)
        assert self.repeat_record.state == State.Success
        assert self.repeat_record.num_attempts == 1
        assert self.repeat_record.attempts[0].state == State.Success
        assert self.repeat_record.attempts[0].message == format_response(resp)

    def test_add_server_failure_attempt_fail(self):
        message = '504: Gateway Timeout'
        self.repeat_record.add_server_failure_attempt(message=message)
        assert self.repeat_record.state == State.Fail
        assert self.repeat_record.num_attempts == 1
        assert self.repeat_record.attempts[0].state == State.Fail
        assert self.repeat_record.attempts[0].message == message
        assert self.repeat_record.attempts[0].traceback == ''

    def test_add_server_failure_attempt_cancel(self):
        message = '504: Gateway Timeout'
        while self.repeat_record.state != State.Cancelled:
            self.repeat_record.add_server_failure_attempt(message=message)

        assert self.repeat_record.num_attempts == MAX_BACKOFF_ATTEMPTS + 1
        attempts = list(self.repeat_record.attempts)
        expected_states = ([State.Fail] * MAX_BACKOFF_ATTEMPTS
                           + [State.Cancelled])
        assert [a.state for a in attempts] == expected_states
        assert attempts[-1].message == message
        assert attempts[-1].traceback == ''

    def test_add_client_failure_attempt_fail(self):
        message = '409: Conflict'
        self.repeat_record.add_client_failure_attempt(message=message)
        assert self.repeat_record.state == State.Fail
        assert self.repeat_record.num_attempts == 1
        assert self.repeat_record.attempts[0].state == State.Fail
        assert self.repeat_record.attempts[0].message == message
        assert self.repeat_record.attempts[0].traceback == ''

    def test_add_client_failure_attempt_cancel(self):
        message = '409: Conflict'
        while self.repeat_record.state != State.Cancelled:
            self.repeat_record.add_client_failure_attempt(message=message)
        assert self.repeat_record.num_attempts == MAX_ATTEMPTS + 1
        attempts = list(self.repeat_record.attempts)
        expected_states = ([State.Fail] * MAX_ATTEMPTS
                           + [State.Cancelled])
        assert [a.state for a in attempts] == expected_states
        assert attempts[-1].message == message
        assert attempts[-1].traceback == ''

    def test_add_client_failure_attempt_no_retry(self):
        message = '422: Unprocessable Entity'
        while self.repeat_record.state != State.Cancelled:
            self.repeat_record.add_client_failure_attempt(message=message, retry=False)
        assert self.repeat_record.num_attempts == 1
        assert self.repeat_record.attempts[0].state == State.Cancelled
        assert self.repeat_record.attempts[0].message == message
        assert self.repeat_record.attempts[0].traceback == ''

    def test_add_payload_error_attempt(self):
        message = 'ValueError: Schema validation failed'
        tb_str = 'Traceback ...'
        self.repeat_record.add_payload_rejected_attempt(message=message,
                                                        traceback_str=tb_str)
        assert self.repeat_record.state == State.PayloadRejected
        # Note: Our payload issues do not affect how we deal with their
        #       server issues:
        assert self.repeat_record.num_attempts == 1
        assert self.repeat_record.attempts[0].state == State.PayloadRejected
        assert self.repeat_record.attempts[0].message == message
        assert self.repeat_record.attempts[0].traceback == tb_str

    def test_cached_attempts(self):
        self.repeat_record.add_client_failure_attempt(message="Fail")

        with self.assertNumQueries(1):
            assert len(self.repeat_record.attempts) == 1
        with self.assertNumQueries(0):
            assert len(self.repeat_record.attempts) == 1

        self.repeat_record.add_client_failure_attempt(message="Fail")

        with self.assertNumQueries(1):
            assert len(self.repeat_record.attempts) == 2
        with self.assertNumQueries(0):
            assert len(self.repeat_record.attempts) == 2


class TestRepeaterHandleResponse(RepeaterTestCase):

    def get_repeat_record(self):
        return self.repeater.repeat_records.create(
            domain=DOMAIN,
            payload_id='cafef00d',
            registered_at=timezone.now(),
        )

    def test_handle_response_success(self):
        resp = RepeaterResponse(
            status_code=200,
            reason='OK',
            text='<h1>Hello World</h1>',
        )
        repeat_record = self.get_repeat_record()
        self.repeater.handle_response(resp, repeat_record)
        assert repeat_record.state == State.Success

    def test_handle_response_429(self):
        resp = RepeaterResponse(
            status_code=429,
            reason='Too Many Requests',
        )
        repeat_record = self.get_repeat_record()
        self.repeater.handle_response(resp, repeat_record)
        assert repeat_record.state == State.Fail

    def test_handle_response_server_failure(self):
        for status_code in HTTP_STATUS_BACK_OFF:
            resp = RepeaterResponse(
                status_code=status_code,
                reason='Retry',
            )
            repeat_record = self.get_repeat_record()
            self.repeater.handle_response(resp, repeat_record)
            assert repeat_record.state == State.Fail

    def test_handle_response_incl_code(self):
        self.repeater.add_backoff_code(404)
        resp = RepeaterResponse(
            status_code=404,
            reason='Repeater-specific retry',
        )
        repeat_record = self.get_repeat_record()
        self.repeater.handle_response(resp, repeat_record)
        assert repeat_record.state == State.Fail

    def test_handle_response_excl_code(self):
        self.repeater.remove_backoff_code(502)
        resp = RepeaterResponse(
            status_code=502,
            reason='Repeater-specific invalid payload',
        )
        repeat_record = self.get_repeat_record()
        self.repeater.handle_response(resp, repeat_record)
        assert repeat_record.state == State.InvalidPayload

    def test_handle_payload_errors(self):
        retry_codes = HTTP_STATUS_BACK_OFF + (HTTPStatus.TOO_MANY_REQUESTS,)
        payload_error_status_codes = (
            s for s in HTTPStatus
            if 400 <= s.value < 600 and s.value not in retry_codes
        )
        for http_status in payload_error_status_codes:
            resp = RepeaterResponse(
                status_code=http_status.value,
                reason='Error',
            )
            repeat_record = self.get_repeat_record()
            self.repeater.handle_response(resp, repeat_record)
            assert repeat_record.state == State.PayloadRejected


class TestConnectionSettingsUsedBy(TestCase):

    def setUp(self):
        super().setUp()
        url = 'https://www.example.com/api/'
        self.conn = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name=url,
            url=url,
        )

    def test_connection_settings_used_by_data_forwarding(self):
        FormRepeater.objects.create(
            domain=DOMAIN,
            connection_settings_id=self.conn.id
        )

        assert self.conn.used_by == {'Data Forwarding'}

    def test_conn_with_no_used_by(self):
        assert self.conn.used_by == set()


class TestRepeaterConnectionSettings(RepeaterTestCase):

    def test_connection_settings_are_accessible(self):
        assert self.repeater.connection_settings.url == 'https://www.example.com/api/'

    def test_used_connection_setting_cannot_be_deleted(self):
        with pytest.raises(ProtectedError):
            self.repeater.connection_settings.delete()
        with pytest.raises(ProtectedError):
            ConnectionSettings.objects.filter(id=self.conn.id).delete()
        with pytest.raises(ProtectedError):
            ConnectionSettings.all_objects.filter(id=self.conn.id).delete()


@patch("corehq.motech.repeaters.tasks.retry_process_repeat_record")
@patch("corehq.motech.repeaters.tasks.process_repeat_record")
class TestAttemptForwardNow(RepeaterTestCase):
    before_now = datetime.utcnow() - timedelta(seconds=1)

    def test_future_next_check(self, process, retry_process):
        rec = self.new_record(next_check=datetime.utcnow() + timedelta(hours=1))
        rec.attempt_forward_now()

        self.assert_not_called(process, retry_process)

    def test_success_state(self, process, retry_process):
        rec = self.new_record(state=State.Success, next_check=None)
        rec.attempt_forward_now()

        self.assert_not_called(process, retry_process)

    def test_cancelled_state(self, process, retry_process):
        rec = self.new_record(state=State.Cancelled, next_check=None)
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

    @flag_enabled('PROCESS_REPEATERS')
    def test_process_repeaters_enabled(self, process, retry_process):
        rec = self.new_record()
        rec.attempt_forward_now()

        self.assert_not_called(process, retry_process)

    @flag_enabled('PROCESS_REPEATERS')
    def test_fire_synchronously_process_repeaters_enabled(
            self,
            process,
            retry_process,
    ):
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

        two = RepeatRecord.objects.get(id=rec.id)
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

    def new_record(self, next_check=before_now, state=State.Pending):
        rec = RepeatRecord(
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
        self.repeater.register(payload, fire_synchronously=True)
        repeat_record = self.repeater.repeat_records.last()
        assert repeat_record.payload_id == payload.get_id
        all_records = list(RepeatRecord.objects.iterate(DOMAIN))
        assert len(all_records) == 1
        assert all_records[0].id == repeat_record.id

    def test_send_request(self):
        case_id = uuid.uuid4().hex
        payload, cases = _create_case(
            domain=DOMAIN, case_id=case_id, case_type='some_case', owner_id='abcd'
        )
        self.repeater.register(payload, fire_synchronously=True)
        repeat_record = self.repeater.repeat_records.last()
        resp = ResponseMock()
        resp.status_code = 200
        resp.reason = 'OK'
        # Basic test checks if send_request is called
        with patch('corehq.motech.repeaters.models.simple_request') as simple_request:
            simple_request.return_value = resp
            self.repeater.send_request(repeat_record, payload)

        assert simple_request.called


class TestFormRepeaterAllowedToForward(RepeaterTestCase):

    def test_white_list_empty(self):
        self.repeater.white_listed_form_xmlns = []
        payload = Mock(xmlns='http://openrosa.org/formdesigner/abc123')
        assert self.repeater.allowed_to_forward(payload)

    def test_payload_white_listed(self):
        self.repeater.white_listed_form_xmlns = [
            'http://openrosa.org/formdesigner/abc123'
        ]
        payload = Mock(xmlns='http://openrosa.org/formdesigner/abc123')
        assert self.repeater.allowed_to_forward(payload)

    def test_payload_not_white_listed(self):
        self.repeater.white_listed_form_xmlns = [
            'http://openrosa.org/formdesigner/abc123'
        ]
        payload = Mock(xmlns='http://openrosa.org/formdesigner/def456')
        assert not self.repeater.allowed_to_forward(payload)

    def test_payload_user_blocked(self):
        self.repeater.user_blocklist = ['deadbeef']
        payload = Mock(user_id='deadbeef')
        assert not self.repeater.allowed_to_forward(payload)


class TestRepeatRecordManager(RepeaterTestCase):
    before_now = datetime.utcnow() - timedelta(days=1)

    def test_count_by_repeater_and_state(self):
        self.make_records(1, state=State.Pending)
        self.make_records(2, state=State.Fail)
        self.make_records(3, state=State.Cancelled)
        self.make_records(5, state=State.Success)
        counts = RepeatRecord.objects.count_by_repeater_and_state(domain=DOMAIN)

        rid = self.repeater.id
        assert counts[rid][State.Pending] == 1
        assert counts[rid][State.Fail] == 2
        assert counts[rid][State.Cancelled] == 3
        assert counts[rid][State.Success] == 5

        missing_id = uuid.uuid4()
        assert counts[missing_id][State.Pending] == 0
        assert counts[missing_id][State.Fail] == 0
        assert counts[missing_id][State.Cancelled] == 0
        assert counts[missing_id][State.Success] == 0

    def test_count_overdue(self):
        now = datetime.utcnow()
        self.new_record(next_check=now - timedelta(hours=2))
        self.new_record(next_check=now - timedelta(hours=1))
        self.new_record(next_check=now - timedelta(minutes=15))
        self.new_record(next_check=now - timedelta(minutes=5))
        self.new_record(next_check=None, state=State.Success)
        overdue = RepeatRecord.objects.count_overdue()
        assert overdue == 3

        with self.pause_repeater():
            overdue = RepeatRecord.objects.count_overdue()
            assert overdue == 0

    @contextmanager
    def pause_repeater(self):
        try:
            self.repeater.is_paused = True
            self.repeater.save()
            yield
        finally:
            self.repeater.is_paused = False
            self.repeater.save()

    iter_partition = RepeatRecord.objects.iter_partition

    def test_one_partition(self):
        iter_partition = type(self).iter_partition
        all_ids = self.make_records(5)
        start = datetime.utcnow()
        ids = {r.id for r in iter_partition(start, 0, 1)}
        assert ids == all_ids

    def test_four_partitions(self):
        iter_partition = type(self).iter_partition
        all_ids = sorted(self.make_records(16))
        start = datetime.utcnow()
        ids0 = [r.id for r in iter_partition(start, 0, 4)]
        ids1 = [r.id for r in iter_partition(start, 1, 4)]
        ids2 = [r.id for r in iter_partition(start, 2, 4)]
        ids3 = [r.id for r in iter_partition(start, 3, 4)]

        assert sorted(ids0 + ids1 + ids2 + ids3) == all_ids
        assert all([ids0, ids1, ids2, ids3]), [ids0, ids1, ids2, ids3]

    def test_partition_start(self):
        iter_partition = type(self).iter_partition
        all_ids = self.make_records(5)
        self.new_record(next_check=datetime.utcnow() + timedelta(hours=1))
        start = datetime.utcnow()
        ids = {r.id for r in iter_partition(start, 0, 1)}
        assert ids == all_ids

    def test_get_domains_with_records(self):
        self.new_record(domain='a')
        self.new_record(domain='b')
        self.new_record(domain='c')
        assert set(RepeatRecord.objects.get_domains_with_records()) == {'a', 'b', 'c'}

    def test_get_domains_with_records_with_filter(self):
        self.new_record(domain='alex')
        self.new_record(domain='alice')
        self.new_record(domain='carl')
        assert (
            set(RepeatRecord.objects.get_domains_with_records().filter(domain__startswith="al"))
            == {'alex', 'alice'}
        )

    def test_get_repeat_record_ids_for_domain(self):
        cancelled = self.new_record(state=State.Cancelled, next_check=None)
        success = self.new_record(state=State.Success, next_check=None)
        self.new_record(domain="exclude")
        ids = RepeatRecord.objects.get_repeat_record_ids(DOMAIN)
        assert Counter([cancelled.id, success.id]) == Counter(ids)

    def test_get_repeat_record_ids_for_repeater(self):
        non_default_repeater = FormRepeater.objects.create(
            domain=DOMAIN,
            connection_settings=self.conn,
        )

        actual = self.new_record_for_repeater(non_default_repeater)
        self.new_record()
        ids = RepeatRecord.objects.get_repeat_record_ids(DOMAIN, repeater_id=non_default_repeater.id)
        assert Counter([actual.id]) == Counter(ids)

    def test_get_repeat_record_ids_for_state(self):
        cancelled = self.new_record(state=State.Cancelled, next_check=None)
        self.new_record(state=State.Success, next_check=None)
        ids = RepeatRecord.objects.get_repeat_record_ids(DOMAIN, state=State.Cancelled)
        assert Counter([cancelled.id]) == Counter(ids)

    def test_get_repeat_record_ids_for_payload(self):
        actual = self.new_record(payload_id="waldo")
        self.new_record(payload_id="not-waldo")
        ids = RepeatRecord.objects.get_repeat_record_ids(DOMAIN, payload_id="waldo")
        assert Counter([actual.id]) == Counter(ids)

    def test_get_repeat_record_ids_with_all_filters(self):
        non_default_repeater = FormRepeater.objects.create(
            domain=DOMAIN,
            connection_settings=self.conn,
        )
        actual = self.new_record_for_repeater(non_default_repeater, state=State.Fail, payload_id="waldo")
        self.new_record_for_repeater(non_default_repeater, state=State.Pending, payload_id="waldo")
        self.new_record_for_repeater(non_default_repeater, state=State.Fail, payload_id="not-waldo")
        self.new_record_for_repeater(self.repeater, state=State.Fail, payload_id="waldo")
        ids = RepeatRecord.objects.get_repeat_record_ids(
            DOMAIN, repeater_id=non_default_repeater.id, state=State.Fail, payload_id="waldo"
        )
        assert Counter([actual.id]) == Counter(ids)

    def test_count(self):
        with (
            make_repeat_record(self.repeater, State.Pending),
            make_repeat_record(self.repeater, State.Pending),
            make_repeat_record(self.repeater, State.Pending),
        ):
            count = RepeatRecord.objects.count_all_ready()
            assert count == 3

    def new_record(self, next_check=before_now, state=State.Pending, domain=DOMAIN, payload_id="c0ffee"):
        return self.new_record_for_repeater(
            self.repeater, next_check=next_check, state=state, domain=domain, payload_id=payload_id
        )

    def new_record_for_repeater(
        self, repeater, next_check=before_now, state=State.Pending, domain=DOMAIN, payload_id="c0ffee"
    ):
        return RepeatRecord.objects.create(
            domain=domain,
            repeater_id=repeater.repeater_id,
            payload_id=payload_id,
            registered_at=self.before_now,
            next_check=next_check,
            state=state,
        )

    def make_records(self, n, domain=DOMAIN, state=State.Pending, payload_id="c0ffee"):
        now = timezone.now() - timedelta(seconds=10)
        is_pending = state in RECORD_QUEUED_STATES
        records = RepeatRecord.objects.bulk_create(RepeatRecord(
            domain=domain,
            repeater=self.repeater,
            payload_id=payload_id,
            registered_at=now,
            next_check=(now if is_pending else None),
            state=state,
        ) for i in range(n))
        return {r.id for r in records}


class TestRepeatRecordMethods(TestCase):

    def test_repeater_returns_active_repeater(self):
        repeater = Repeater.objects.create(
            domain=self.domain,
            connection_settings=self.conn_settings,
            is_deleted=False
        )
        repeat_record = RepeatRecord.objects.create(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=repeater.repeater_id
        )

        assert repeat_record.repeater is not None

    def test_repeater_returns_deleted_repeater(self):
        repeater = Repeater.objects.create(
            domain=self.domain,
            connection_settings=self.conn_settings,
            is_deleted=True
        )
        repeat_record = RepeatRecord.objects.create(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=repeater.repeater_id
        )

        assert repeat_record.repeater.is_deleted

    def test_repeater_raises_if_not_found(self):
        repeat_record = RepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id='404aaaaaaaaaaaaaaaaaaaaaaaaaa404',
        )

        with pytest.raises(Repeater.DoesNotExist):
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
        record = RepeatRecord.objects.create(
            domain="test",
            repeater_id=self.repeater.id.hex,
            payload_id="abc123",
            state=State.Empty,
            registered_at=now - timedelta(hours=1),
        )
        record.requeue()

        assert record.state == State.Pending
        assert record.next_check <= datetime.utcnow()

    def test_get_payload(self):
        record = RepeatRecord(
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
        record = RepeatRecord(
            domain="test",
            repeater_id=self.repeater.id.hex,
            payload_id="abc123",
            registered_at=now - hour,
        )
        with travel(now, tick=False):
            record.postpone_by(3 * hour)
        assert record.next_check == now + 3 * hour


class TestRepeatRecordMethodsNoDB(SimpleTestCase):
    domain = 'repeat-record-tests'

    def test_exceeded_max_retries_returns_false_if_fewer_tries_than_possible(self):
        repeat_record = RepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            state=State.Fail
        )

        with (
            patch.object(RepeatRecord, "num_attempts", 0),
            patch.object(repeat_record, "max_possible_tries", 1)
        ):
            assert not repeat_record.exceeded_max_retries

    def test_exceeded_max_retries_returns_true_if_equal(self):
        repeat_record = RepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            state=State.Fail
        )

        with (
            patch.object(RepeatRecord, "num_attempts", 1),
            patch.object(repeat_record, "max_possible_tries", 1)
        ):
            assert repeat_record.exceeded_max_retries

    def test_exceeded_max_retries_returns_true_if_more_tries_than_possible(self):
        repeat_record = RepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            state=State.Fail
        )

        with (
            patch.object(RepeatRecord, "num_attempts", 2),
            patch.object(repeat_record, "max_possible_tries", 1)
        ):
            assert repeat_record.exceeded_max_retries

    def test_exceeded_max_retries_returns_false_if_not_failure_state(
            self):
        repeat_record = RepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            state=State.Success,
        )

        with (
            patch.object(RepeatRecord, "num_attempts", 2),
            patch.object(repeat_record, "max_possible_tries", 1)
        ):
            assert not repeat_record.exceeded_max_retries


class TestIsSuccessResponse(SimpleTestCase):

    def test_true_response(self):
        assert is_success_response(True)

    def test_status_201_response(self):
        response = Mock(status_code=201)
        assert is_success_response(response)

    def test_status_404_response(self):
        response = Mock(status_code=404)
        assert not is_success_response(response)

    def test_none_response(self):
        assert not is_success_response(None)


class TestDataSourceUpdateManager(TestCase):

    def test_get_oldest_date(self):
        ten_days_ago = datetime.today() - timedelta(days=10)
        with travel(ten_days_ago, tick=False):
            DataSourceUpdate.objects.create(
                domain='test-domain',
                data_source_id=uuid4(),
                doc_ids=['doc_1']
            )
        DataSourceUpdate.objects.create(
            domain='test-domain',
            data_source_id=uuid4(),
            doc_ids=['doc_2']
        )
        oldest_date = DataSourceUpdate.objects.get_oldest_date()
        assert oldest_date.date() == ten_days_ago.date()

    def test_get_oldest_date_none(self):
        oldest_date = DataSourceUpdate.objects.get_oldest_date()
        assert oldest_date is None


@use('db')
@fixture
def connect_conn_fixture():
    url = COMMCARE_CONNECT_URL
    conn = ConnectionSettings.objects.create(domain=DOMAIN, name=url, url=url)
    try:
        yield conn
    finally:
        conn.delete()


@use(connect_conn_fixture)
def test_forwards_to_connect():
    conn = connect_conn_fixture()
    repeater = FormRepeater(domain=DOMAIN, connection_settings_id=conn.id)
    assert forwards_to_commcare_connect(repeater)


@use('db')
@fixture
def other_conn_fixture():
    url = 'https://example.com/api/'
    conn = ConnectionSettings.objects.create(domain=DOMAIN, name=url, url=url)
    try:
        yield conn
    finally:
        conn.delete()


@use(other_conn_fixture)
def test_doesnt_forward_to_connect():
    conn = other_conn_fixture()
    repeater = FormRepeater(domain=DOMAIN, connection_settings_id=conn.id)
    assert not forwards_to_commcare_connect(repeater)
