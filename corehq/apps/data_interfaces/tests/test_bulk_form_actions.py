from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

import pytest

from corehq.apps.data_interfaces.bulk_form_actions import (
    SAVE_EVERY,
    SKIPPED,
    SUCCEEDED,
    FormAction,
    FormActionResult,
    _apply_form_action,
    _save_interval,
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

    def test_persists_progress_before_completion(self):
        # A small job (interval == 1) must persist counts as it goes, not only
        # at completion, so the status poll's progress bar advances.
        forms = [create_form_for_test(DOMAIN, state=XFormInstance.NORMAL) for _ in range(3)]
        job = self._job(BulkAsyncJob.Action.ARCHIVE, [f.form_id for f in forms])
        seen = []
        original_save = job.save

        def record_processed(*args, **kwargs):
            seen.append(job.processed_count)
            return original_save(*args, **kwargs)

        job.save = record_processed
        run_bulk_form_action(job)

        assert seen == [0, 1, 2, 3, 3]


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


@pytest.mark.parametrize("requested_count, expected", [
    (0, SAVE_EVERY),   # empty job: guard against ZeroDivisionError, value unused
    (1, 1),
    (5, 1),            # tiny jobs save after every form
    (20, 1),
    (40, 2),
    (100, 5),          # ~5% steps
    (2000, SAVE_EVERY),  # first size that reaches the cap
    (10000, SAVE_EVERY),  # very large jobs stay capped
])
def test_save_interval(requested_count, expected):
    assert _save_interval(requested_count) == expected


class TestApplyFormAction(SimpleTestCase):

    def _patched_apply_form_action(self, form_ids, forms, form_action):
        with patch(
            'corehq.apps.data_interfaces.bulk_form_actions.XFormInstance.objects.iter_forms',
            return_value=forms,
        ):
            return list(_apply_form_action(DOMAIN, form_ids, form_action))

    def test_empty_form_ids(self):
        assert self._patched_apply_form_action([], [], FormAction(run=lambda f: None)) == []

    def test_success(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        calls = []
        results = self._patched_apply_form_action(['f1'], [form], FormAction(run=calls.append))
        assert calls == [form]
        assert results == [FormActionResult('f1', SUCCEEDED)]

    def test_missing_is_not_found(self):
        results = self._patched_apply_form_action(['missing'], [], FormAction(run=lambda f: None))
        assert results == [FormActionResult('missing', SKIPPED, 'not_found')]

    def test_wrong_domain_is_not_found(self):
        form = Mock(form_id='f1', domain='other-domain')
        called = []
        results = self._patched_apply_form_action(['f1'], [form], FormAction(run=called.append))
        assert called == []  # action not applied to out-of-domain forms
        assert results == [FormActionResult('f1', SKIPPED, 'not_found')]

    def test_exception_is_unexpected_error(self):
        form = Mock(form_id='f1', domain=DOMAIN)

        def unexpected_error(xform):
            raise Exception('error')

        with patch(
            'corehq.apps.data_interfaces.bulk_form_actions.notify_exception'
        ) as notify:
            results = self._patched_apply_form_action(['f1'], [form], FormAction(run=unexpected_error))
        assert results == [FormActionResult('f1', SKIPPED, 'unexpected_error')]
        notify.assert_called_once()

    def test_mixed_results(self):
        found = Mock(form_id='f1', domain=DOMAIN)
        results = self._patched_apply_form_action(['f1', 'missing'], [found], FormAction(run=lambda f: None))
        assert results == [
            FormActionResult('f1', SUCCEEDED),
            FormActionResult('missing', SKIPPED, 'not_found'),
        ]

    def test_validate_skip_reason(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        acted = []
        results = self._patched_apply_form_action(
            ['f1'], [form],
            FormAction(run=acted.append, validate=lambda f: 'not_archived'),
        )
        assert acted == []  # validation skip means action is never applied
        assert results == [FormActionResult('f1', SKIPPED, 'not_archived')]

    def test_validate_pass_runs_action(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        results = self._patched_apply_form_action(
            ['f1'], [form], FormAction(run=lambda f: None, validate=lambda f: None),
        )
        assert results == [FormActionResult('f1', SUCCEEDED)]
