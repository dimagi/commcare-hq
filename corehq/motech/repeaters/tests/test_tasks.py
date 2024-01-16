from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.utils.xform import (
    FormSubmissionBuilder,
    TestFormMetadata,
)
from corehq.motech.models import ConnectionSettings, RequestLog
from corehq.motech.repeaters.dbaccessors import delete_all_repeat_records
from corehq.motech.repeaters.models import FormRepeater, SQLRepeatRecord, Repeater
from corehq.motech.repeaters.tasks import (
    _process_repeat_record,
    delete_old_request_logs,
    process_repeater,
)
from ..const import State

DOMAIN = 'gaidhlig'
PAYLOAD_IDS = ['aon', 'dha', 'trì', 'ceithir', 'coig', 'sia', 'seachd', 'ochd',
               'naoi', 'deich']


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


class TestProcessRepeater(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(DOMAIN)
        cls.addClassCleanup(cls.domain.delete)
        cls.connection_settings = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name='Test API',
            url="http://localhost/api/"
        )
        cls.addClassCleanup(delete_all_repeat_records)

    def setUp(self):
        self.repeater = FormRepeater.objects.create(
            domain=DOMAIN,
            format='form_xml',
            connection_settings=self.connection_settings
        )
        just_now = timezone.now() - timedelta(seconds=10)
        for payload_id in PAYLOAD_IDS:
            self.repeater.repeat_records.create(
                domain=self.repeater.domain,
                payload_id=payload_id,
                registered_at=just_now,
            )
            just_now += timedelta(seconds=1)

    def test_get_payload_fails(self):
        # If the payload of a repeat record is missing, it should be
        # cancelled, and process_repeater() should continue to the next
        # payload
        with patch('corehq.motech.repeaters.models.log_repeater_error_in_datadog'), \
                patch('corehq.motech.repeaters.tasks.metrics_counter'):
            process_repeater(self.repeater.id)

        # All records were tried and cancelled
        records = list(self.repeater.repeat_records.all())
        self.assertEqual(len(records), 10)
        self.assertTrue(all(r.state == State.Cancelled for r in records))
        # All records have a cancelled Attempt
        self.assertTrue(all(len(r.attempts) == 1 for r in records))
        self.assertTrue(all(r.attempts[0].state == State.Cancelled for r in records))

    def test_send_request_fails(self):
        # If send_request() should be retried with the same repeat
        # record, process_repeater() should exit
        with patch('corehq.motech.repeaters.models.simple_request') as post_mock, \
                patch('corehq.motech.repeaters.tasks.metrics_counter'), \
                form_context(PAYLOAD_IDS):
            post_mock.return_value = Mock(status_code=400, reason='Bad request', text='')
            process_repeater(self.repeater.id)

        # Only the first record was attempted, the rest are still pending
        states = [r.state for r in self.repeater.repeat_records.all()]
        self.assertListEqual(states, ([State.Fail] + [State.Pending] * 9))


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
        repeat_record = SQLRepeatRecord(
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

        repeat_record = SQLRepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=self.repeater.repeater_id,
        )

        _process_repeat_record(repeat_record)

        fetched_repeat_record = SQLRepeatRecord.objects.get(id=repeat_record.id)
        self.assertEqual(fetched_repeat_record.state, State.Cancelled)
        self.assertEqual(self.mock_fire.call_count, 0)
        self.assertEqual(self.mock_postpone_by.call_count, 0)

    def test_cancels_and_returns_if_repeat_record_exceeds_max_retries(self):
        repeat_record = SQLRepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=self.repeater.repeater_id,
            state=State.Fail,
        )

        with patch.object(SQLRepeatRecord, "num_attempts", 1), \
                patch.object(repeat_record, "max_possible_tries", 1):
            _process_repeat_record(repeat_record)

        fetched_repeat_record = SQLRepeatRecord.objects.get(id=repeat_record.id)
        self.assertEqual(fetched_repeat_record.state, State.Cancelled)
        self.assertEqual(self.mock_fire.call_count, 0)
        self.assertEqual(self.mock_postpone_by.call_count, 0)

    def test_deletes_repeat_record_cancels_and_returns_if_repeater_deleted(self):
        deleted_repeater = Repeater.objects.create(
            domain=self.domain,
            connection_settings=self.conn_settings,
            is_deleted=True
        )

        repeat_record = SQLRepeatRecord(
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

        repeat_record = SQLRepeatRecord(
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

        repeat_record = SQLRepeatRecord(
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

        repeat_record = SQLRepeatRecord(
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
        cls.addClassCleanup(delete_all_repeat_records)

    def setUp(self):
        self.patch()

    def patch(self):
        patch_fire = patch.object(SQLRepeatRecord, 'fire')
        self.mock_fire = patch_fire.start()
        self.addCleanup(patch_fire.stop)

        patch_postpone_by = patch.object(SQLRepeatRecord, 'postpone_by')
        self.mock_postpone_by = patch_postpone_by.start()
        self.addCleanup(patch_postpone_by.stop)

        patch_domain_can_forward = patch('corehq.motech.repeaters.tasks.domain_can_forward')
        self.mock_domain_can_forward = patch_domain_can_forward.start()
        self.mock_domain_can_forward.return_value = True
        self.addCleanup(patch_domain_can_forward.stop)
