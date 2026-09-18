from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase
from django.contrib.auth.models import User

import pytest

from corehq.apps.data_interfaces.bulk_form_actions import (
    MAX_SAVE_INTERVAL,
    NOT_FOUND,
    SKIPPED,
    SUCCEEDED,
    UNEXPECTED_ERROR,
    BulkFormActionError,
    FormActionResult,
    _apply_form_action,
    _apply_to_each,
    _save_interval,
    build_form_action,
    create_bulk_form_job,
    mark_job_failed,
    run_bulk_form_action,
)
from corehq.apps.data_interfaces.models import BulkAsyncJob
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import HQApiKey, WebUser
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.form_processor.models.forms import XFormInstance
from corehq.form_processor.tests.utils import create_form_for_test, sharded

DOMAIN = 'bulk-actions-test'
USERNAME = 'abc@example.com'


class TestBuildFormAction(TestCase):

    def _job(self, action):
        return BulkAsyncJob(
            domain=DOMAIN, model=XFormInstance, action=action, requested_by='u',
        )

    def test_archive_action(self):
        action_fn = build_form_action(self._job(BulkAsyncJob.Action.ARCHIVE), user_id='uid')
        assert callable(action_fn)

    def test_unarchive_action(self):
        action_fn = build_form_action(self._job(BulkAsyncJob.Action.UNARCHIVE), user_id='uid')
        assert callable(action_fn)

    def test_unsupported_action(self):
        with pytest.raises(BulkFormActionError):
            build_form_action(self._job('UNKNOWN'), user_id='uid')


@sharded
class TestRunBulkFormAction(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.blob_db = TemporaryFilesystemBlobDB()
        cls.addClassCleanup(cls.blob_db.close)
        cls.domain = create_domain(DOMAIN)
        cls.addClassCleanup(cls.domain.delete)
        cls.user = WebUser.create(DOMAIN, USERNAME, '***', None, None)
        cls.addClassCleanup(cls.user.delete, None, None)

    def _job(self, action, form_ids, username=USERNAME):
        job = BulkAsyncJob(
            domain=DOMAIN, model=XFormInstance, action=action, requested_by=username,
        )
        job.set_requested_ids(form_ids)
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
        assert job.get_skipped() == {NOT_FOUND: ['does-not-exist']}

    def test_unarchive_already_unarchived_is_noop(self):
        # unarchive is idempotent: a normal form is a no-op success, not a skip
        normal = create_form_for_test(DOMAIN, state=XFormInstance.NORMAL)
        job = self._job(BulkAsyncJob.Action.UNARCHIVE, [normal.form_id])
        run_bulk_form_action(job)
        job.refresh_from_db()
        assert job.succeeded_count == 1
        assert job.get_skipped() == {}

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

    def test_unknown_user_raises_error(self):
        job = self._job(BulkAsyncJob.Action.ARCHIVE, ['form-1'], username='unknown')

        with pytest.raises(BulkFormActionError):
            run_bulk_form_action(job)

        job.refresh_from_db()
        assert job.status == BulkAsyncJob.Status.FAILED
        assert job.started_at is None
        assert job.completed_at is not None

    def test_unsupported_action_raises_error(self):
        job = self._job('UNKNOWN', ['form-1'])

        with pytest.raises(BulkFormActionError):
            run_bulk_form_action(job)

        job.refresh_from_db()
        assert job.status == BulkAsyncJob.Status.FAILED
        assert job.started_at is None
        assert job.completed_at is not None


class TestCreateBulkFormJob(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.blob_db = TemporaryFilesystemBlobDB()
        cls.addClassCleanup(cls.blob_db.close)

    def test_api_key_defaults_to_none(self):
        job = create_bulk_form_job(
            DOMAIN, BulkAsyncJob.Action.ARCHIVE, USERNAME, ['form-1'])
        job.refresh_from_db()
        assert job.api_key is None

    def test_api_key_is_recorded(self):
        django_user = User.objects.create_user(USERNAME)
        api_key = HQApiKey.objects.create(
            user=django_user, name='test-key')

        job = create_bulk_form_job(
            DOMAIN,
            BulkAsyncJob.Action.ARCHIVE,
            USERNAME,
            ['form-1'],
            api_key=api_key,
        )

        job.refresh_from_db()
        assert job.api_key == api_key


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
    (0, 1),
    (1, 1),
    (5, 1),
    (40, 2),
    (100, 5),
    (2000, 100),
    (10000, 100),
])
def test_save_interval(requested_count, expected):
    assert _save_interval(requested_count) == expected


def _successful_action(forms):
    for form in forms:
        yield FormActionResult(form.form_id, SUCCEEDED)


class TestApplyFormAction(SimpleTestCase):

    def _patched_apply_form_action(self, form_ids, forms, action_fn=_successful_action):
        with patch(
            'corehq.apps.data_interfaces.bulk_form_actions.XFormInstance.objects.iter_forms',
            return_value=forms,
        ):
            return list(_apply_form_action(DOMAIN, form_ids, action_fn))

    def test_empty_form_ids(self):
        assert self._patched_apply_form_action([], []) == []

    def test_success(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        results = self._patched_apply_form_action(['f1'], [form])
        assert results == [FormActionResult('f1', SUCCEEDED)]

    def test_missing_is_not_found(self):
        results = self._patched_apply_form_action(['missing'], [])
        assert results == [FormActionResult('missing', SKIPPED, NOT_FOUND)]

    def test_wrong_domain_is_not_found(self):
        # the action never sees it, so there is no success to report
        form = Mock(form_id='f1', domain='other-domain')
        results = self._patched_apply_form_action(['f1'], [form])
        assert results == [FormActionResult('f1', SKIPPED, NOT_FOUND)]

    def test_mixed_results(self):
        found = Mock(form_id='f1', domain=DOMAIN)
        results = self._patched_apply_form_action(['f1', 'missing'], [found])
        assert results == [
            FormActionResult('f1', SUCCEEDED),
            FormActionResult('missing', SKIPPED, NOT_FOUND),
        ]

    def test_forms_are_handed_to_the_action_in_batches(self):
        forms = [
            Mock(form_id=f'f{i}', domain=DOMAIN)
            for i in range(MAX_SAVE_INTERVAL + 1)
        ]
        sizes = []

        def record_size(batch):
            sizes.append(len(batch))
            yield from _successful_action(batch)

        self._patched_apply_form_action(
            [f.form_id for f in forms], forms, record_size)

        assert sizes == [MAX_SAVE_INTERVAL, 1]


class TestApplyToEach(SimpleTestCase):

    def test_success(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        calls = []
        results = list(_apply_to_each([form], calls.append))
        assert calls == [form]
        assert results == [FormActionResult('f1', SUCCEEDED)]

    def test_exception_is_unexpected_error(self):
        form = Mock(form_id='f1', domain=DOMAIN)

        def unexpected_error(xform):
            raise Exception('error')

        with patch(
            'corehq.apps.data_interfaces.bulk_form_actions.notify_exception'
        ) as notify:
            results = list(_apply_to_each([form], unexpected_error))
        assert results == [FormActionResult('f1', SKIPPED, UNEXPECTED_ERROR)]
        notify.assert_called_once()

    def test_one_failure_does_not_stop_the_batch(self):
        forms = [Mock(form_id=f'f{i}', domain=DOMAIN) for i in range(3)]

        def fail_on_second(xform):
            if xform.form_id == 'f1':
                raise Exception('error')

        with patch('corehq.apps.data_interfaces.bulk_form_actions.notify_exception'):
            results = list(_apply_to_each(forms, fail_on_second))

        assert results == [
            FormActionResult('f0', SUCCEEDED),
            FormActionResult('f1', SKIPPED, UNEXPECTED_ERROR),
            FormActionResult('f2', SUCCEEDED),
        ]
