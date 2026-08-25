from datetime import datetime

import pytest
from django.test import SimpleTestCase, TestCase

from corehq.apps.data_interfaces.api.bulk_form_action import (
    MAX_FORM_IDS,
    UserError,
    serialize_job,
    validate_payload,
)
from corehq.apps.data_interfaces.models import BulkAsyncJob
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.form_processor.models import XFormInstance

DOMAIN = 'bulk-action-api-test'


@pytest.mark.parametrize("action", ['archive', 'unarchive'])
def test_valid_actions_are_accepted(action):
    assert validate_payload({'action': action, 'form_ids': ['a']}) == (action, ['a'])


def test_max_form_ids_is_accepted():
    form_ids = [str(i) for i in range(MAX_FORM_IDS)]
    assert validate_payload(
        {'action': 'archive', 'form_ids': form_ids}) == ('archive', form_ids)


def test_too_many_form_ids_raises():
    form_ids = [str(i) for i in range(MAX_FORM_IDS + 1)]
    with pytest.raises(UserError):
        validate_payload({'action': 'archive', 'form_ids': form_ids})


def test_payload_must_be_an_object():
    with pytest.raises(UserError):
        validate_payload(['not', 'a', 'dict'])


def test_missing_action_raises():
    with pytest.raises(UserError):
        validate_payload({'form_ids': ['a']})


def test_missing_form_ids_raises():
    with pytest.raises(UserError):
        validate_payload({'action': 'archive'})


@pytest.mark.parametrize("action", [
    None,
    'destroy',
    'delete',
    ['archive'],
])
def test_invalid_action_raises(action):
    with pytest.raises(UserError):
        validate_payload({'action': action, 'form_ids': ['a']})


@pytest.mark.parametrize("form_ids", [
    [],
    'abc',
    {'a': 1},
    ['a', 1],
    ['a', ''],
    ['a', None],
])
def test_invalid_form_ids_raise(form_ids):
    with pytest.raises(UserError):
        validate_payload({'action': 'archive', 'form_ids': form_ids})


class TestSerializeJob(SimpleTestCase):
    """Jobs are built unsaved: serialization reads no blob until done."""

    def _job(self, **kwargs):
        job = BulkAsyncJob(
            domain=DOMAIN,
            model=XFormInstance,
            action=BulkAsyncJob.Action.ARCHIVE,
            requested_by='user@example.com',
            requested_count=10,
            **kwargs,
        )
        job.created_at = datetime(2026, 8, 25, 14, 2, 11, 930000)
        return job

    def test_pending_job(self):
        data = serialize_job(self._job(status=BulkAsyncJob.Status.PENDING))
        assert data['action'] == 'archive'
        assert data['status'] == 'pending'
        assert data['requested_by'] == 'user@example.com'
        assert data['requested'] == 10
        assert data['processed'] == 0
        assert data['succeeded'] == 0
        assert data['skipped'] == {}
        assert data['created_at'] == '2026-08-25T14:02:11.930000Z'
        assert data['started_at'] is None
        assert data['completed_at'] is None

    def test_running_job_reports_partial_counts(self):
        job = self._job(
            status=BulkAsyncJob.Status.RUNNING,
            processed_count=4,
            succeeded_count=3,
        )
        job.started_at = datetime(2026, 8, 25, 14, 2, 12, 104000)

        data = serialize_job(job)

        assert data['status'] == 'running'
        assert data['processed'] == 4
        assert data['succeeded'] == 3
        assert data['skipped'] == {}  # blob is not written until the job is done
        assert data['started_at'] == '2026-08-25T14:02:12.104000Z'
        assert data['completed_at'] is None

    def test_failed_job(self):
        job = self._job(status=BulkAsyncJob.Status.FAILED)
        job.completed_at = datetime(2026, 8, 25, 14, 3, 40, 882000)

        data = serialize_job(job)

        assert data['status'] == 'failed'
        assert data['skipped'] == {}
        assert data['completed_at'] == '2026-08-25T14:03:40.882000Z'

    def test_id_is_hex_without_dashes(self):
        data = serialize_job(self._job(status=BulkAsyncJob.Status.PENDING))
        assert '-' not in data['id']
        assert len(data['id']) == 32


class TestSerializeCompletedJob(TestCase):
    """A done job reads its skipped ids from blob storage."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.blob_db = TemporaryFilesystemBlobDB()
        cls.addClassCleanup(cls.blob_db.close)

    def test_complete_job_returns_skipped_buckets(self):
        job = BulkAsyncJob(
            domain=DOMAIN,
            model=XFormInstance,
            action=BulkAsyncJob.Action.ARCHIVE,
            requested_by='user@example.com',
            status=BulkAsyncJob.Status.COMPLETE,
            processed_count=3,
            succeeded_count=1,
        )
        job.set_requested_ids(['a', 'b', 'c'])
        job.save()
        job.set_skipped({'not_found': ['b'], 'unexpected_error': ['c']})
        job.save()

        data = serialize_job(job)

        assert data['status'] == 'complete'
        assert data['requested'] == 3
        assert data['succeeded'] == 1
        assert data['skipped'] == {'not_found': ['b'], 'unexpected_error': ['c']}
