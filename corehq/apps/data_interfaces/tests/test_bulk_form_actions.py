from django.test import TestCase

from corehq.apps.data_interfaces.bulk_form_actions import (
    build_form_action,
    mark_job_failed,
    run_bulk_form_action,
)
from corehq.apps.data_interfaces.models import BulkAsyncJob
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.form_processor.models.forms import XFormInstance
from corehq.form_processor.tests.utils import create_form_for_test, sharded

DOMAIN = 'bulk-actions-test'


class TestBuildFormAction(TestCase):

    def _job(self, action):
        return BulkAsyncJob(
            domain=DOMAIN, model=XFormInstance, action=action, requested_by='u',
        )

    def test_archive_action(self):
        form_action = build_form_action(self._job(BulkAsyncJob.Action.ARCHIVE), user_id='uid')
        assert form_action.validate is None

    def test_unarchive_action_validates_already_unarchived(self):
        form_action = build_form_action(self._job(BulkAsyncJob.Action.UNARCHIVE), user_id='uid')
        archived = create_form_for_test(DOMAIN, state=XFormInstance.ARCHIVED, save=False)
        normal = create_form_for_test(DOMAIN, state=XFormInstance.NORMAL, save=False)
        assert form_action.validate(archived) is None
        assert form_action.validate(normal) == 'already_unarchived'


@sharded
class TestRunBulkFormAction(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.blob_db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.blob_db.close()
        super().tearDownClass()

    def _job(self, action, form_ids):
        job = BulkAsyncJob(
            domain=DOMAIN, model=XFormInstance, action=action, requested_by='u',
        )
        stored = job.set_requested_ids(form_ids)
        job.requested_count = len(stored)
        job.save()
        return job

    def test_archive_marks_complete_and_counts(self):
        form = create_form_for_test(DOMAIN, state=XFormInstance.NORMAL)
        job = self._job(BulkAsyncJob.Action.ARCHIVE, [form.form_id])

        run_bulk_form_action(job)

        job.refresh_from_db()
        assert job.status == BulkAsyncJob.Status.COMPLETE
        assert job.started_at is not None and job.completed_at is not None
        assert job.processed_count == 1
        assert job.succeeded_count == 1
        assert job.get_skipped() == {}
        assert XFormInstance.objects.get_form(form.form_id, DOMAIN).is_archived

    def test_missing_id_recorded_not_found(self):
        job = self._job(BulkAsyncJob.Action.ARCHIVE, ['does-not-exist'])
        run_bulk_form_action(job)
        job.refresh_from_db()
        assert job.succeeded_count == 0
        assert job.get_skipped() == {'not_found': ['does-not-exist']}

    def test_unarchive_skips_already_unarchived(self):
        normal = create_form_for_test(DOMAIN, state=XFormInstance.NORMAL)
        job = self._job(BulkAsyncJob.Action.UNARCHIVE, [normal.form_id])
        run_bulk_form_action(job)
        job.refresh_from_db()
        assert job.get_skipped() == {'already_unarchived': [normal.form_id]}


class TestMarkJobFailed(TestCase):

    def _job(self, status):
        job = BulkAsyncJob(
            domain=DOMAIN, model=XFormInstance,
            action=BulkAsyncJob.Action.ARCHIVE, requested_by='u', status=status,
        )
        job.save()
        return job

    def test_marks_pending_job_failed(self):
        job = self._job(BulkAsyncJob.Status.PENDING)
        mark_job_failed(job.id)
        job.refresh_from_db()
        assert job.status == BulkAsyncJob.Status.FAILED
        assert job.completed_at is not None

    def test_does_not_touch_completed_job(self):
        job = self._job(BulkAsyncJob.Status.COMPLETE)
        mark_job_failed(job.id)
        job.refresh_from_db()
        assert job.status == BulkAsyncJob.Status.COMPLETE

    def test_missing_job_is_noop(self):
        mark_job_failed('00000000-0000-0000-0000-000000000000')  # no error
