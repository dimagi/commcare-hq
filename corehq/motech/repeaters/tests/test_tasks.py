from collections import namedtuple
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from freezegun import freeze_time

from corehq.motech.models import ConnectionSettings, RequestLog
from corehq.util.test_utils import flag_enabled

from ..const import State
from ..models import FormRepeater, Repeater, RepeatRecord
from ..tasks import (
    _get_wait_duration_seconds,
    _process_repeat_record,
    delete_old_request_logs,
    get_repeater_ids_by_domain,
    iter_ready_repeater_ids,
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
        pairs = list(iter_ready_repeater_ids())
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

    @ patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_resets_backoff_on_success(self, mock_get_repeater, __):
        repeat_record_states = [State.Success, State.Fail, State.Empty, None]
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater
        update_repeater(repeat_record_states, 1, 'token')

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_called_once()

    @ patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_resets_backoff_on_invalid(self, mock_get_repeater, __):
        repeat_record_states = [State.InvalidPayload, State.Fail, State.Empty, None]
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater
        update_repeater(repeat_record_states, 1, 'token')

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_called_once()

    @ patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_sets_backoff_on_failure(self, mock_get_repeater, __):
        repeat_record_states = [State.Fail, State.Empty, None]
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater
        update_repeater(repeat_record_states, 1, 'token')

        mock_repeater.set_backoff.assert_called_once()
        mock_repeater.reset_backoff.assert_not_called()

    @ patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_does_nothing_on_empty(self, mock_get_repeater, __):
        repeat_record_states = [State.Empty]
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater
        update_repeater(repeat_record_states, 1, 'token')

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_not_called()

    @ patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_does_nothing_on_none(self, mock_get_repeater, __):
        repeat_record_states = [None]
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater
        update_repeater(repeat_record_states, 1, 'token')

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_not_called()


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
