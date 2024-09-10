from collections import namedtuple
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from nose.tools import assert_equal

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.utils.xform import (
    FormSubmissionBuilder,
    TestFormMetadata,
)
from corehq.motech.models import ConnectionSettings, RequestLog
from corehq.motech.repeaters.models import FormRepeater, Repeater, RepeatRecord
from corehq.motech.repeaters.tasks import (
    _process_repeat_record,
    delete_old_request_logs,
    get_repeater_ids_by_domain,
    iter_ready_repeater_ids_forever,
    iter_ready_repeater_ids_once,
    process_repeater,
    update_repeater,
)
from corehq.util.test_utils import _create_case, flag_enabled

from ..const import State

DOMAIN = 'gaidhlig'
PAYLOAD_IDS = ['aon', 'dha', 'trì', 'ceithir', 'coig', 'sia', 'seachd', 'ochd',
               'naoi', 'deich']


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


@contextmanager
def form_context(form_ids):
    for form_id in form_ids:
        builder = FormSubmissionBuilder(
            form_id=form_id,
            metadata=TestFormMetadata(domain=DOMAIN),
        )
        submit_form_locally(builder.as_xml_string(), DOMAIN)
    try:
        yield
    finally:
        XFormInstance.objects.hard_delete_forms(DOMAIN, form_ids)


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


class TestIterReadyRepeaterIDsForever(SimpleTestCase):

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
            self.assertFalse(next(iter_ready_repeater_ids_forever(), False))

    def test_domain_cant_forward_now(self):
        with (
            patch('corehq.motech.repeaters.tasks.Repeater.objects.get_all_ready_ids_by_domain',
                  side_effect=self.all_ready_ids_by_domain()),
            patch('corehq.motech.repeaters.tasks.domain_can_forward_now',
                  return_value=False),  # <--
            patch('corehq.motech.repeaters.tasks.toggles.PROCESS_REPEATERS.get_enabled_domains',
                  return_value=['domain1', 'domain2', 'domain3']),
        ):
            self.assertFalse(next(iter_ready_repeater_ids_forever(), False))

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
            self.assertFalse(next(iter_ready_repeater_ids_forever(), False))

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
            patch('corehq.motech.repeaters.tasks.get_repeater_lock'),
        ):
            repeaters = list(iter_ready_repeater_ids_forever())
            self.assertEqual(len(repeaters), 9)
            repeater_ids = [(r[0], r[1]) for r in repeaters]
            self.assertEqual(repeater_ids, [
                # First loop
                ('domain1', 'repeater_id1'),
                ('domain2', 'repeater_id4'),
                ('domain3', 'repeater_id6'),
                ('domain1', 'repeater_id2'),
                ('domain2', 'repeater_id5'),
                ('domain1', 'repeater_id3'),

                # Second loop
                ('domain1', 'repeater_id1'),
                ('domain2', 'repeater_id4'),
                ('domain1', 'repeater_id2'),
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
            patch('corehq.motech.repeaters.tasks.get_repeater_lock'),
        ):
            repeaters = list(iter_ready_repeater_ids_forever())
            self.assertEqual(len(repeaters), 7)
            repeater_ids = [(r[0], r[1]) for r in repeaters]
            self.assertEqual(repeater_ids, [
                ('domain1', 'repeater_id1'),
                ('domain3', 'repeater_id6'),
                ('domain1', 'repeater_id2'),
                ('domain2', 'repeater_id5'),
                ('domain1', 'repeater_id3'),
                ('domain1', 'repeater_id1'),
                ('domain1', 'repeater_id2'),
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
            patch('corehq.motech.repeaters.tasks.get_repeater_lock'),
        ):
            repeaters = list(iter_ready_repeater_ids_forever())
            self.assertEqual(len(repeaters), 4)
            repeater_ids = [(r[0], r[1]) for r in repeaters]
            self.assertEqual(repeater_ids, [
                ('domain2', 'repeater_id4'),
                ('domain3', 'repeater_id6'),
                ('domain2', 'repeater_id5'),
                ('domain2', 'repeater_id4'),
            ])


def test_iter_ready_repeater_ids_once():
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
        pairs = list(iter_ready_repeater_ids_once())
        assert_equal(pairs, [
            # First round of domains
            ('domain1', 'repeater_id1'),
            ('domain2', 'repeater_id4'),
            ('domain3', 'repeater_id6'),

            # Second round
            ('domain1', 'repeater_id2'),
            ('domain2', 'repeater_id5'),

            # Third round
            ('domain1', 'repeater_id3'),
        ])


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
        assert_equal(repeater_ids_by_domain, {
            'domain2': ['repeater_id4', 'repeater_id5'],
            'domain3': ['repeater_id6'],
        })


@flag_enabled('PROCESS_REPEATERS')
class TestProcessRepeater(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        can_forward_now_patch = patch(
            'corehq.motech.repeaters.tasks.domain_can_forward_now',
            return_value=True,
        )
        can_forward_now_patch = can_forward_now_patch.start()
        cls.addClassCleanup(can_forward_now_patch.stop)

        cls.set_backoff_patch = patch.object(FormRepeater, 'set_backoff')
        cls.set_backoff_patch.start()
        cls.addClassCleanup(cls.set_backoff_patch.stop)

        connection_settings = ConnectionSettings.objects.create(
            domain=DOMAIN,
            url='http://www.example.com/api/'
        )
        cls.repeater = FormRepeater.objects.create(
            domain=DOMAIN,
            connection_settings=connection_settings,
        )

    def test_process_repeater_sends_repeat_record(self):
        payload, __ = _create_case(
            domain=DOMAIN,
            case_id=str(uuid4()),
            case_type='case',
            owner_id='abc123'
        )
        self.repeater.register(payload)

        with (
            patch('corehq.motech.repeaters.models.simple_request') as request_mock,
            patch('corehq.motech.repeaters.tasks.get_repeater_lock')
        ):
            request_mock.return_value = ResponseMock(status_code=200, reason='OK')
            process_repeater(DOMAIN, self.repeater.repeater_id, 'token')

            request_mock.assert_called_once()

    def test_process_repeater_updates_repeater(self):
        payload, __ = _create_case(
            domain=DOMAIN,
            case_id=str(uuid4()),
            case_type='case',
            owner_id='abc123'
        )
        self.repeater.register(payload)

        with (
            patch('corehq.motech.repeaters.models.simple_request') as request_mock,
            patch('corehq.motech.repeaters.tasks.get_repeater_lock')
        ):
            request_mock.return_value = ResponseMock(
                status_code=429,
                reason='Too Many Requests',
            )
            process_repeater(DOMAIN, self.repeater.repeater_id, 'token')

        self.repeater.set_backoff.assert_called_once()


@flag_enabled('PROCESS_REPEATERS')
class TestUpdateRepeater(SimpleTestCase):

    @patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_resets_backoff_on_success(self, mock_get_repeater, __):
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater

        update_repeater([State.Success, State.Fail, State.Empty, None], 1, 'token')

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_called_once()

    @patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_sets_backoff_on_failure(self, mock_get_repeater, __):
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater

        update_repeater([State.Fail, State.Empty, None], 1, 'token')

        mock_repeater.set_backoff.assert_called_once()
        mock_repeater.reset_backoff.assert_not_called()

    @patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_does_nothing_on_empty(self, mock_get_repeater, __):
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater

        update_repeater([State.Empty], 1, 'token')

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_not_called()

    @patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_does_nothing_on_none(self, mock_get_repeater, __):
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater

        update_repeater([None], 1, 'token')

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_not_called()
