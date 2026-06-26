import uuid

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from corehq.apps.data_interfaces.models import BulkAsyncJob
from corehq.apps.users.models import HQApiKey
from corehq.form_processor.models import XFormInstance


class BulkAsyncJobChoicesTests(SimpleTestCase):
    def test_action_choices_cover_spec(self):
        assert set(BulkAsyncJob.Action.values) == {'archive', 'unarchive', 'delete'}

    def test_status_choices_cover_spec(self):
        assert set(BulkAsyncJob.Status.values) == {'pending', 'running', 'complete', 'failed'}


class BulkAsyncJobModelTests(TestCase):
    def test_defaults_for_new_job(self):
        job = BulkAsyncJob.objects.create(
            domain='test-domain',
            model=XFormInstance,
            action=BulkAsyncJob.Action.DELETE,
            requested_by='admin@example.com',
            requested_ids_blob_key='req-key',
            skipped_ids_blob_key='skip-key',
            requested_count=10,
        )
        job.refresh_from_db()
        assert isinstance(job.id, uuid.UUID)
        assert job.status == BulkAsyncJob.Status.PENDING
        assert job.model is XFormInstance
        assert job.action == 'delete'
        assert job.processed_count == 0
        assert job.succeeded_count == 0
        assert job.started_at is None
        assert job.completed_at is None
        assert job.created_at is not None
        assert job.api_key is None

    def test_deleting_api_key_nulls_fk(self):
        user = User.objects.create(username='u@example.com')
        api_key = HQApiKey.objects.create(user=user, name='k')
        job = BulkAsyncJob.objects.create(
            domain='d',
            model=XFormInstance,
            action=BulkAsyncJob.Action.ARCHIVE,
            requested_by='u@example.com',
            api_key=api_key,
            requested_ids_blob_key='r',
            skipped_ids_blob_key='s',
            requested_count=0,
        )
        api_key.delete()
        job.refresh_from_db()
        assert job.api_key is None
