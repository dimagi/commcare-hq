"""Execution logic for bulk form actions (archive/unarchive).

Kept separate from ``tasks.py`` so the job lifecycle can be tested without
Celery. The Celery task is a thin wrapper around ``run_bulk_form_action``.
"""
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Callable, Optional

from attrs import frozen

from corehq.apps.data_interfaces.models import BulkAsyncJob
from corehq.apps.data_interfaces.utils import SUCCEEDED, apply_form_action
from corehq.apps.users.models import CouchUser

log = logging.getLogger(__name__)

SAVE_EVERY = 100


@frozen
class FormAction:
    run: Callable
    validate: Optional[Callable] = None


def build_form_action(job, user_id):
    """Return the ``FormAction`` for ``job.action``."""
    if job.action == BulkAsyncJob.Action.ARCHIVE:
        return FormAction(run=lambda f: f.archive(user_id=user_id))
    if job.action == BulkAsyncJob.Action.UNARCHIVE:
        return FormAction(
            run=lambda f: f.unarchive(user_id=user_id),
            validate=lambda f: None if f.is_archived else 'already_unarchived',
        )
    raise ValueError(f'unknown bulk action: {job.action}')


def run_bulk_form_action(job):
    """Execute ``job`` start to finish, updating counts and status on the row."""
    job.status = BulkAsyncJob.Status.RUNNING
    job.started_at = datetime.now(tz=UTC)
    job.save()

    user_id = _resolve_user_id(job.requested_by)
    form_ids = job.get_requested_ids()
    form_action = build_form_action(job, user_id)

    skipped = defaultdict(list)
    processed = succeeded = 0
    for result in apply_form_action(
        job.domain, form_ids, form_action.run, validate=form_action.validate,
    ):
        processed += 1
        if result.status == SUCCEEDED:
            succeeded += 1
        else:
            skipped[result.reason].append(result.form_id)
        if processed % SAVE_EVERY == 0:
            job.processed_count = processed
            job.succeeded_count = succeeded
            job.save(update_fields=['processed_count', 'succeeded_count'])
            log.info(
                "bulk_%s bulk_async_job_id=%s domain=%s processed=%s/%s",
                job.action, job.id, job.domain, processed, job.requested_count,
            )

    job.processed_count = processed
    job.succeeded_count = succeeded
    job.set_skipped(dict(skipped))
    job.status = BulkAsyncJob.Status.COMPLETE
    job.completed_at = datetime.now(tz=UTC)
    job.save()


def mark_job_failed(job_id):
    """Mark a job ``failed`` unless it already reached a terminal state."""
    try:
        job = BulkAsyncJob.objects.get(id=job_id)
    except BulkAsyncJob.DoesNotExist:
        return
    if job.is_done:
        return
    job.status = BulkAsyncJob.Status.FAILED
    job.completed_at = datetime.now(tz=UTC)
    job.save()


def _resolve_user_id(username):
    user = CouchUser.get_by_username(username)
    if user is None:
        log.warning("bulk form action: user %s not found; using user_id=None", username)
        return None
    return user.user_id
