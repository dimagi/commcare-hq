from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.utils.xform import (
    FormSubmissionBuilder,
    TestFormMetadata,
)
from corehq.motech.models import ConnectionSettings, RequestLog
from corehq.motech.repeaters.models import Repeater, RepeatRecord
from corehq.motech.repeaters.tasks import (
    _process_repeat_record,
    delete_old_request_logs,
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
