from collections import namedtuple
from datetime import datetime, timedelta
from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase, TestCase

import pytest
from freezegun import freeze_time

from corehq.motech.models import ConnectionSettings, RequestLog
from corehq.util.test_utils import flag_enabled

from ..const import State
from ..models import FormRepeater, Repeater, RepeatRecord
from ..tasks import (
    RepeaterLock,
    _get_wait_duration_seconds,
    _process_repeat_record,
    delete_old_request_logs,
    get_repeater_ids_by_domain,
    iter_filtered_repeater_ids,
    iter_ready_domain_repeater_ids,
    process_repeaters,
    update_repeater,
)

DOMAIN = 'test-tasks'


ResponseMock = namedtuple('ResponseMock', 'status_code reason')


class TestDeleteOldRequestLogs(TestCase):

    def test_raw_delete_logs_old(self):
        log = RequestLog.objects.create(domain=DOMAIN)
        log.timestamp = datetime.utcnow() - timedelta(days=43)
        log.save()  # Replace the value set by auto_now_add=True
        delete_old_request_logs.apply()

        count = RequestLog.objects.filter(domain=DOMAIN).count()
        self.assertEqual(count, 0)

    def test_raw_delete_logs_new(self):
        log = RequestLog.objects.create(domain=DOMAIN)
        log.timestamp = datetime.utcnow() - timedelta(days=41)
        log.save()
        delete_old_request_logs.apply()

        count = RequestLog.objects.filter(domain=DOMAIN).count()
        self.assertGreater(count, 0)

    def test_num_queries_per_chunk(self):
        log = RequestLog.objects.create(domain=DOMAIN)
        log.timestamp = datetime.utcnow() - timedelta(days=91)
        log.save()

        with self.assertNumQueries(3):
            delete_old_request_logs.apply()

    def test_num_queries_chunked(self):
        for __ in range(10):
            log = RequestLog.objects.create(domain=DOMAIN)
            log.timestamp = datetime.utcnow() - timedelta(days=91)
            log.save()

        with patch('corehq.motech.repeaters.tasks.DELETE_CHUNK_SIZE', 2):
            with self.assertNumQueries(11):
                delete_old_request_logs.apply()

        count = RequestLog.objects.filter(domain=DOMAIN).count()
        self.assertEqual(count, 0)


class TestProcessRepeatRecord(TestCase):

    def test_returns_if_record_is_cancelled(self):
        repeat_record = RepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=self.repeater.repeater_id,
            next_check=None,
            state=State.Cancelled,
        )

        _process_repeat_record(repeat_record)

        self.assertEqual(self.mock_fire.call_count, 0)
        self.assertEqual(self.mock_postpone_by.call_count, 0)

    def test_cancels_and_returns_if_domain_cannot_forward(self):
        self.mock_domain_can_forward.return_value = False

        repeat_record = RepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=self.repeater.repeater_id,
        )

        _process_repeat_record(repeat_record)

        fetched_repeat_record = RepeatRecord.objects.get(id=repeat_record.id)
        self.assertEqual(fetched_repeat_record.state, State.Cancelled)
        self.assertEqual(self.mock_fire.call_count, 0)
        self.assertEqual(self.mock_postpone_by.call_count, 0)

    def test_cancels_and_returns_if_repeat_record_exceeds_max_retries(self):
        repeat_record = RepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=self.repeater.repeater_id,
            state=State.Fail,
        )

        with patch.object(RepeatRecord, "num_attempts", 1), \
                patch.object(repeat_record, "max_possible_tries", 1):
            _process_repeat_record(repeat_record)

        fetched_repeat_record = RepeatRecord.objects.get(id=repeat_record.id)
        self.assertEqual(fetched_repeat_record.state, State.Cancelled)
        self.assertEqual(self.mock_fire.call_count, 0)
        self.assertEqual(self.mock_postpone_by.call_count, 0)

    def test_deletes_repeat_record_cancels_and_returns_if_repeater_deleted(self):
        deleted_repeater = Repeater.objects.create(
            domain=self.domain,
            connection_settings=self.conn_settings,
            is_deleted=True
        )

        repeat_record = RepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=deleted_repeater.repeater_id,
        )

        _process_repeat_record(repeat_record)

        repeat_record.refresh_from_db(fields=["state"])
        self.assertEqual(repeat_record.state, State.Cancelled)
        self.assertEqual(self.mock_fire.call_count, 0)
        self.assertEqual(self.mock_postpone_by.call_count, 0)

    def test_postpones_record_if_repeater_is_paused(self):
        paused_repeater = Repeater.objects.create(
            domain=self.domain,
            connection_settings=self.conn_settings,
            is_paused=True
        )

        repeat_record = RepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=paused_repeater.repeater_id,
        )

        _process_repeat_record(repeat_record)

        self.assertEqual(self.mock_fire.call_count, 0)
        self.assertEqual(self.mock_postpone_by.call_count, 1)

    def test_fires_record_if_repeater_is_not_paused(self):
        paused_repeater = Repeater.objects.create(
            domain=self.domain,
            connection_settings=self.conn_settings,
            is_paused=False
        )

        repeat_record = RepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=paused_repeater.repeater_id,
        )

        _process_repeat_record(repeat_record)

        self.assertEqual(self.mock_fire.call_count, 1)
        self.assertEqual(self.mock_postpone_by.call_count, 0)

    def test_payload_error_metrics(self):
        with (
            patch('corehq.motech.repeaters.tasks.metrics_histogram') as mock_metrics,
            patch('corehq.motech.repeaters.tasks.logging') as mock_logging,
        ):
            repeater = FormRepeater.objects.create(
                domain=self.domain,
                connection_settings=self.conn_settings,
            )
            repeat_record = RepeatRecord(
                domain=self.domain,
                payload_id='does-not-exist',
                registered_at=datetime.utcnow(),
                repeater_id=repeater.repeater_id,
            )
            _process_repeat_record(repeat_record)
            mock_logging.exception.assert_not_called()
            mock_metrics.assert_called_once()

    def test_paused_and_deleted_repeater_does_not_fire_or_postpone(self):
        paused_and_deleted_repeater = Repeater.objects.create(
            domain=self.domain,
            connection_settings=self.conn_settings,
            is_paused=True,
            is_deleted=True,
        )

        repeat_record = RepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=paused_and_deleted_repeater.repeater_id,
        )

        _process_repeat_record(repeat_record)

        self.assertEqual(self.mock_fire.call_count, 0)
        self.assertEqual(self.mock_postpone_by.call_count, 0)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'process-repeat-record-tests'
        cls.conn_settings = ConnectionSettings.objects.create(
            domain=cls.domain,
            name='To Be Deleted',
            url="http://localhost/api/"
        )
        cls.repeater = Repeater.objects.create(
            domain=cls.domain,
            connection_settings=cls.conn_settings,
        )

    def setUp(self):
        self.patch()

    def patch(self):
        patch_fire = patch.object(RepeatRecord, 'fire')
        self.mock_fire = patch_fire.start()
        self.addCleanup(patch_fire.stop)

        patch_postpone_by = patch.object(RepeatRecord, 'postpone_by')
        self.mock_postpone_by = patch_postpone_by.start()
        self.addCleanup(patch_postpone_by.stop)

        patch_domain_can_forward = patch('corehq.motech.repeaters.tasks.domain_can_forward')
        self.mock_domain_can_forward = patch_domain_can_forward.start()
        self.mock_domain_can_forward.return_value = True
        self.addCleanup(patch_domain_can_forward.stop)


class TestProcessRepeaters(TestCase):

    @patch('corehq.motech.repeaters.tasks.get_redis_lock')
    @patch('corehq.motech.repeaters.tasks.get_redis_connection')
    @patch('corehq.motech.repeaters.tasks.iter_filtered_repeater_ids')
    @patch('corehq.motech.repeaters.tasks.process_repeater')
    def test_one_group(
        self,
        mock_process_repeater,
        mock_iter_filtered_repeater_ids,
        mock_get_redis_connection,
        __,
    ):
        mock_redis = MagicMock()
        mock_redis.get.return_value = 1
        mock_get_redis_connection.return_value = mock_redis
        mock_iter_filtered_repeater_ids.side_effect = [
            ['repeater_id1'],
            [],
        ]

        process_repeaters()
        mock_process_repeater.assert_called_once()

    @patch('corehq.motech.repeaters.tasks.get_redis_lock')
    @patch('corehq.motech.repeaters.tasks.uuid.uuid1')
    @patch('corehq.motech.repeaters.tasks.get_redis_connection')
    @patch('corehq.motech.repeaters.tasks.iter_filtered_repeater_ids')
    @patch('corehq.motech.repeaters.tasks.process_repeater')
    def test_two_groups(
        self,
        mock_process_repeater,
        mock_iter_filtered_repeater_ids,
        mock_get_redis_connection,
        mock_uuid1,
        __,
    ):
        mock_redis = MagicMock()
        mock_redis.get.return_value = 1
        mock_get_redis_connection.return_value = mock_redis
        mock_iter_filtered_repeater_ids.side_effect = [
            ['repeater_id1', 'repeater_id2'],
            ['repeater_id3'],
            [],
        ]
        mock_uuid1.return_value.hex = 'token'

        process_repeaters()
        mock_process_repeater.assert_has_calls([
            call('repeater_id1', 'token', 0),
            call('repeater_id2', 'token', 0),
            call('repeater_id3', 'token', 1),
        ])

    @patch('corehq.motech.repeaters.tasks.get_redis_lock')
    @patch('corehq.motech.repeaters.tasks.process_repeater')
    @patch('corehq.motech.repeaters.tasks.get_redis_connection')
    @patch('corehq.motech.repeaters.tasks.iter_filtered_repeater_ids')
    @patch('corehq.motech.repeaters.tasks.time')
    def test_sleep(
            self,
            mock_time,
            mock_iter_filtered_repeater_ids,
            mock_get_redis_connection,
            __,
            _,
    ):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = [0, 0, 1]
        mock_get_redis_connection.return_value = mock_redis
        mock_iter_filtered_repeater_ids.side_effect = [
            ['repeater_id1'],
            [],
        ]

        process_repeaters()
        mock_time.sleep.assert_has_calls([
            call.sleep(0.1),
            call.sleep(0.1),
        ])


def test_iter_ready_repeater_ids():
    with (
        patch(
            'corehq.motech.repeaters.tasks.Repeater.objects.get_all_ready_ids_by_domain',
            return_value={
                'domain1': ['repeater_id1', 'repeater_id2', 'repeater_id3'],
                'domain2': ['repeater_id4', 'repeater_id5'],
                'domain3': ['repeater_id6'],
            }
        ),
        patch(
            'corehq.motech.repeaters.tasks.toggles.PROCESS_REPEATERS.get_enabled_domains',
            return_value=['domain1', 'domain2', 'domain3'],
        ),
    ):
        pairs = list(iter_ready_domain_repeater_ids())
        assert pairs == [
            # First round of domains
            ('domain1', 'repeater_id3'),
            ('domain2', 'repeater_id5'),
            ('domain3', 'repeater_id6'),

            # Second round
            ('domain1', 'repeater_id2'),
            ('domain2', 'repeater_id4'),

            # Third round
            ('domain1', 'repeater_id1'),
        ]


def test_get_repeater_ids_by_domain():
    with (
        patch(
            'corehq.motech.repeaters.tasks.Repeater.objects.get_all_ready_ids_by_domain',
            return_value={
                'domain1': ['repeater_id1', 'repeater_id2', 'repeater_id3'],
                'domain2': ['repeater_id4', 'repeater_id5'],
                'domain3': ['repeater_id6'],
            }
        ),
        patch(
            'corehq.motech.repeaters.tasks.toggles.PROCESS_REPEATERS.get_enabled_domains',
            return_value=['domain2', 'domain4'],
        ),
        patch(
            'corehq.motech.repeaters.tasks.toggles.PROCESS_REPEATERS.enabled',
            side_effect=lambda dom, __: dom == 'domain3'),
    ):
        repeater_ids_by_domain = get_repeater_ids_by_domain()
        assert repeater_ids_by_domain == {
            'domain2': ['repeater_id4', 'repeater_id5'],
            'domain3': ['repeater_id6'],
        }


@flag_enabled('PROCESS_REPEATERS')
class TestUpdateRepeater(SimpleTestCase):

    @patch('corehq.motech.repeaters.tasks.get_redis_connection')
    @patch('corehq.motech.repeaters.tasks.RepeaterLock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_resets_backoff_on_success(self, mock_get_repeater, __, _):
        repeat_record_states = [State.Success, State.Fail, State.Empty, None]
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater
        update_repeater(repeat_record_states, 1, 'token', 0)

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_called_once()

    @patch('corehq.motech.repeaters.tasks.get_redis_connection')
    @patch('corehq.motech.repeaters.tasks.RepeaterLock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_resets_backoff_on_invalid(self, mock_get_repeater, __, _):
        repeat_record_states = [State.InvalidPayload, State.Fail, State.Empty, None]
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater
        update_repeater(repeat_record_states, 1, 'token', 0)

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_called_once()

    @patch('corehq.motech.repeaters.tasks.get_redis_connection')
    @patch('corehq.motech.repeaters.tasks.RepeaterLock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_backs_off_on_failure(
        self,
        mock_get_repeater,
        mock_get_repeater_lock,
        __,
    ):
        repeat_record_states = [State.Fail, State.Empty, None]
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater
        mock_lock = MagicMock()
        mock_get_repeater_lock.return_value = mock_lock
        update_repeater(repeat_record_states, 1, 'token', 0)

        mock_repeater.set_backoff.assert_called_once()
        mock_repeater.reset_backoff.assert_not_called()
        mock_lock.release.assert_called_once()

    @patch('corehq.motech.repeaters.tasks.get_redis_connection')
    @patch('corehq.motech.repeaters.tasks.RepeaterLock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_does_nothing_on_empty(self, mock_get_repeater, __, _):
        repeat_record_states = [State.Empty]
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater
        update_repeater(repeat_record_states, 1, 'token', 0)

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_not_called()

    @patch('corehq.motech.repeaters.tasks.get_redis_connection')
    @patch('corehq.motech.repeaters.tasks.RepeaterLock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_does_nothing_on_none(self, mock_get_repeater, __, _):
        repeat_record_states = [None]
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater
        update_repeater(repeat_record_states, 1, 'token', 0)

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_not_called()

    @patch('corehq.motech.repeaters.tasks.get_redis_connection')
    @patch('corehq.motech.repeaters.tasks.RepeaterLock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_releases_lock(
        self,
        mock_get_repeater,
        mock_get_repeater_lock,
        mock_get_redis_connection,
    ):
        repeat_record_states = [None]
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater
        mock_lock = MagicMock()
        mock_get_repeater_lock.return_value = mock_lock
        mock_redis = MagicMock()
        mock_get_redis_connection.return_value = mock_redis
        update_repeater(repeat_record_states, 1, 'token', 0)

        mock_lock.release.assert_called_once()
        mock_redis.incr.assert_called_once()


@freeze_time('2025-01-01')
class TestGetWaitDurationSeconds(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.repeater = FormRepeater.objects.create(
            domain=DOMAIN,
            connection_settings=ConnectionSettings.objects.create(
                domain=DOMAIN,
                url='http://www.example.com/api/'
            ),
        )

    def test_repeat_record_no_attempts(self):
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        repeat_record = RepeatRecord.objects.create(
            repeater=self.repeater,
            domain=DOMAIN,
            payload_id='abc123',
            registered_at=five_minutes_ago,
        )
        wait_duration = _get_wait_duration_seconds(repeat_record)
        self.assertEqual(wait_duration, 300)

    def test_repeat_record_one_attempt(self):
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        repeat_record = RepeatRecord.objects.create(
            repeater=self.repeater,
            domain=DOMAIN,
            payload_id='abc123',
            registered_at=five_minutes_ago,
        )
        thirty_seconds_ago = datetime.utcnow() - timedelta(seconds=30)
        repeat_record.attempt_set.create(
            created_at=thirty_seconds_ago,
            state=State.Fail,
        )
        wait_duration = _get_wait_duration_seconds(repeat_record)
        self.assertEqual(wait_duration, 30)

    def test_repeat_record_two_attempts(self):
        an_hour_ago = datetime.utcnow() - timedelta(hours=1)
        repeat_record = RepeatRecord.objects.create(
            repeater=self.repeater,
            domain=DOMAIN,
            payload_id='abc123',
            registered_at=an_hour_ago,
        )
        thirty_minutes = datetime.utcnow() - timedelta(minutes=30)
        repeat_record.attempt_set.create(
            created_at=thirty_minutes,
            state=State.Fail,
        )
        five_seconds_ago = datetime.utcnow() - timedelta(seconds=5)
        repeat_record.attempt_set.create(
            created_at=five_seconds_ago,
            state=State.Fail,
        )
        wait_duration = _get_wait_duration_seconds(repeat_record)
        self.assertEqual(wait_duration, 5)


class TestRepeaterLock(TestCase):

    def test_lock_name(self):
        lock = RepeaterLock('abc123')
        self.assertEqual(lock._lock.name, 'process_repeater_abc123')

    def test_acquire(self):
        RepeaterLock.timeout = 1
        lock = RepeaterLock('repeater_id')
        assert lock.acquire()
        assert lock.token

    def test_acquire_assert(self):
        lock = RepeaterLock('repeater_id', 'lock_token')
        with pytest.raises(AssertionError, match=r'.* already acquired .*'):
            lock.acquire()

    def test_reacquire_assert(self):
        lock = RepeaterLock('repeater_id')
        with pytest.raises(AssertionError, match=r'Missing lock token'):
            lock.reacquire()

    def test_release_assert(self):
        lock = RepeaterLock('repeater_id')
        with pytest.raises(AssertionError, match=r'Missing lock token'):
            lock.release()

    @staticmethod
    def _get_repeater():
        return FormRepeater.objects.create(
            domain=DOMAIN,
            connection_settings=ConnectionSettings.objects.create(
                domain=DOMAIN,
                url='http://www.example.com/api/'
            ),
        )


class TestIterFilteredRepeaterIDs(SimpleTestCase):

    @staticmethod
    def all_ready_ids_by_domain():
        return [
            {
                # See test_iter_ready_repeater_ids_once()
                'domain1': ['repeater_id1', 'repeater_id2', 'repeater_id3'],
                'domain2': ['repeater_id4', 'repeater_id5'],
                'domain3': ['repeater_id6'],
            },
            {
                'domain1': ['repeater_id1', 'repeater_id2'],
                'domain2': ['repeater_id4']
            },
            {},
        ]

    def test_no_ready_repeaters(self):
        with (
            patch('corehq.motech.repeaters.tasks.Repeater.objects.get_all_ready_ids_by_domain',
                  return_value={}),  # <--
            patch('corehq.motech.repeaters.tasks.domain_can_forward_now',
                  return_value=True),
            patch('corehq.motech.repeaters.tasks.toggles.PROCESS_REPEATERS.get_enabled_domains',
                  return_value=['domain1', 'domain2', 'domain3']),
        ):
            self.assertFalse(next(iter_filtered_repeater_ids(), False))

    def test_domain_cant_forward_now(self):
        with (
            patch('corehq.motech.repeaters.tasks.Repeater.objects.get_all_ready_ids_by_domain',
                  side_effect=self.all_ready_ids_by_domain()),
            patch('corehq.motech.repeaters.tasks.domain_can_forward_now',
                  return_value=False),  # <--
            patch('corehq.motech.repeaters.tasks.toggles.PROCESS_REPEATERS.get_enabled_domains',
                  return_value=['domain1', 'domain2', 'domain3']),
        ):
            self.assertFalse(next(iter_filtered_repeater_ids(), False))

    def test_process_repeaters_not_enabled(self):
        with (
            patch('corehq.motech.repeaters.tasks.Repeater.objects.get_all_ready_ids_by_domain',
                  side_effect=self.all_ready_ids_by_domain()),
            patch('corehq.motech.repeaters.tasks.domain_can_forward_now',
                  return_value=True),
            patch('corehq.motech.repeaters.tasks.toggles.PROCESS_REPEATERS.get_enabled_domains',
                  return_value=[]),  # <--
            patch('corehq.motech.repeaters.tasks.toggles.PROCESS_REPEATERS.enabled',
                  return_value=False),  # <--
        ):
            self.assertFalse(next(iter_filtered_repeater_ids(), False))

    def test_successive_loops(self):
        with (
            patch('corehq.motech.repeaters.tasks.Repeater.objects.get_all_ready_ids_by_domain',
                  side_effect=self.all_ready_ids_by_domain()),
            patch('corehq.motech.repeaters.tasks.domain_can_forward_now',
                  return_value=True),
            patch('corehq.motech.repeaters.tasks.toggles.PROCESS_REPEATERS.get_enabled_domains',
                  return_value=['domain1', 'domain2', 'domain3']),
            patch('corehq.motech.repeaters.tasks.rate_limit_repeater',
                  return_value=False),
        ):
            repeater_ids = list(iter_filtered_repeater_ids())
            self.assertEqual(repeater_ids, [
                'repeater_id3',  # domain1
                'repeater_id5',  # domain2
                'repeater_id6',  # domain3
                'repeater_id2',  # domain1
                'repeater_id4',  # domain2
                'repeater_id1',  # domain1
            ])
            repeater_ids = list(iter_filtered_repeater_ids())
            self.assertEqual(repeater_ids, [
                'repeater_id2',  # domain1
                'repeater_id4',  # domain2
                'repeater_id1',  # domain1
            ])

    def test_rate_limit(self):
        with (
            patch('corehq.motech.repeaters.tasks.Repeater.objects.get_all_ready_ids_by_domain',
                  side_effect=self.all_ready_ids_by_domain()),
            patch('corehq.motech.repeaters.tasks.domain_can_forward_now',
                  return_value=True),
            patch('corehq.motech.repeaters.tasks.toggles.PROCESS_REPEATERS.get_enabled_domains',
                  return_value=['domain1', 'domain2', 'domain3']),
            patch('corehq.motech.repeaters.tasks.rate_limit_repeater',
                  side_effect=lambda dom, rep: dom == 'domain2' and rep == 'repeater_id4'),
        ):
            repeater_ids = list(iter_filtered_repeater_ids())
            self.assertEqual(repeater_ids, [
                'repeater_id3',  # domain1
                'repeater_id5',  # domain2
                'repeater_id6',  # domain3
                'repeater_id2',  # domain1
                'repeater_id1',  # domain1
            ])
            repeater_ids = list(iter_filtered_repeater_ids())
            self.assertEqual(repeater_ids, [
                'repeater_id2',  # domain1
                'repeater_id1',  # domain1
            ])

    def test_disabled_domains_excluded(self):
        with (
            patch('corehq.motech.repeaters.tasks.Repeater.objects.get_all_ready_ids_by_domain',
                  side_effect=self.all_ready_ids_by_domain()),
            patch('corehq.motech.repeaters.tasks.domain_can_forward_now',
                  return_value=True),
            patch('corehq.motech.repeaters.tasks.toggles.PROCESS_REPEATERS.get_enabled_domains',
                  return_value=['domain2']),  # <--
            patch('corehq.motech.repeaters.tasks.toggles.PROCESS_REPEATERS.enabled',
                  side_effect=lambda dom, __: dom == 'domain3'),  # <--
            patch('corehq.motech.repeaters.tasks.rate_limit_repeater',
                  return_value=False),
        ):
            repeater_ids = list(iter_filtered_repeater_ids())
            self.assertEqual(repeater_ids, [
                'repeater_id5',  # domain2
                'repeater_id6',  # domain3
                'repeater_id4',  # domain2
            ])
            repeater_ids = list(iter_filtered_repeater_ids())
            self.assertEqual(repeater_ids, [
                'repeater_id4',  # domain2
            ])
