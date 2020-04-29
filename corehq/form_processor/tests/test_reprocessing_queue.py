import uuid
from datetime import datetime, timedelta

from django.test import TestCase

from couchforms.models import UnfinishedSubmissionStub

from corehq.form_processor.management.commands.run_submission_reprocessing_queue import (
    get_unfinished_stub_ids_to_process,
)


def _create_stub(timestamp_offset_mins=31, date_queued_offset_hours=None, attempts=0):
    date_queued = None
    if date_queued_offset_hours is not None:
        date_queued = datetime.utcnow() - timedelta(hours=date_queued_offset_hours)
    return UnfinishedSubmissionStub.objects.create(
        xform_id=uuid.uuid4().hex,
        timestamp=datetime.utcnow() - timedelta(minutes=timestamp_offset_mins),
        date_queued=date_queued,
        attempts=attempts
    )


class TestReprocessingQueue(TestCase):
    BACKOFF_INTERVAL = 7
    BACKOFF_FACTOR = 3

    def tearDown(self):
        UnfinishedSubmissionStub.objects.all().delete()

    def test_get_stubs_early_cutoff(self):
        stubs = [
            _create_stub(29),
            _create_stub(31)
        ]
        ids = get_unfinished_stub_ids_to_process()
        self.assertEqual(ids, [stubs[1].id])

    def test_get_stubs_backoff(self):
        expected = []
        for attempts in (0, 1, 2):
            factor = self.BACKOFF_FACTOR ** attempts
            # create one stub on either side of the window, only the 2nd stub is expected to be returned
            stubs = [
                _create_stub(date_queued_offset_hours=(self.BACKOFF_INTERVAL - 0.1) * factor, attempts=attempts),
                _create_stub(date_queued_offset_hours=(self.BACKOFF_INTERVAL + 0.1) * factor, attempts=attempts)
            ]
            expected.append(stubs[1].id)
        ids = get_unfinished_stub_ids_to_process()
        self.assertEqual(ids, expected)

    def test_get_stubs_max_attempts(self):
        expected = [_create_stub(attempts=7).id]
        _create_stub(attempts=8)
        ids = get_unfinished_stub_ids_to_process()
        self.assertEqual(ids, expected)

    def test_get_stubs_max_backoff(self):
        # after 5 attempts the date filter should be constant
        offset = (self.BACKOFF_INTERVAL + 0.1) * (self.BACKOFF_FACTOR ** 5)
        stubs = [
            _create_stub(date_queued_offset_hours=offset, attempts=5),
            _create_stub(date_queued_offset_hours=offset, attempts=6),
            _create_stub(date_queued_offset_hours=offset, attempts=7),
        ]
        expected = [stub.id for stub in stubs]
        ids = get_unfinished_stub_ids_to_process()
        self.assertEqual(ids, expected)

    def test_large_attempts(self):
        _create_stub(date_queued_offset_hours=1, attempts=60)
        get_unfinished_stub_ids_to_process()
