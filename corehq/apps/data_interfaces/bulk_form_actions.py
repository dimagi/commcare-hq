"""Execution logic for bulk form actions (archive/unarchive).

Kept separate from ``tasks.py`` so the job lifecycle can be tested without
Celery. The Celery task is a thin wrapper around ``run_bulk_form_action``.
"""
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial

from dimagi.utils.chunked import chunked
from dimagi.utils.logging import notify_exception

from corehq.apps.data_interfaces.models import BulkAsyncJob
from corehq.apps.users.models import CouchUser
from corehq.blobs import get_blob_db
from corehq.blobs.atomic import AtomicBlobs
from corehq.form_processor.models import XFormInstance

log = logging.getLogger(__name__)

SUCCEEDED = 'succeeded'
SKIPPED = 'skipped'

MAX_SAVE_INTERVAL = 100

# the API passes these keys back, so changing these values is
# effectively a breaking change for callers
NOT_FOUND = 'not_found'
UNEXPECTED_ERROR = 'unexpected_error'


class BulkFormActionError(Exception):
    """A job cannot be run because its row is invalid"""


@dataclass(frozen=True)
class FormActionResult:
    """Outcome of a bulk form action for a single requested form id."""
    form_id: str
    status: str  # SUCCEEDED | SKIPPED
    reason: str | None = None  # NOT_FOUND | UNEXPECTED_ERROR


def run_bulk_form_action(job):
    """Execute ``job`` start to finish, updating counts and status on the row."""
    try:
        user_id = _resolve_user_id(job.requested_by)
        action_fn = build_form_action(job, user_id)
    except BulkFormActionError:
        mark_job_failed(job.id)
        raise

    job.status = BulkAsyncJob.Status.RUNNING
    job.started_at = datetime.now(tz=UTC)
    job.save()

    form_ids = job.get_requested_ids()
    save_interval = _save_interval(job.requested_count)

    skipped = defaultdict(list)
    processed = succeeded = 0
    for result in _apply_form_action(job.domain, form_ids, action_fn):
        processed += 1
        if result.status == SUCCEEDED:
            succeeded += 1
        else:
            skipped[result.reason].append(result.form_id)
        if processed % save_interval == 0:
            job.processed_count = processed
            job.succeeded_count = succeeded
            job.save(update_fields=['processed_count', 'succeeded_count'])
            log.info(
                "bulk_%s bulk_async_job_id=%s domain=%s processed=%s/%s",
                job.action, job.id, job.domain, processed, job.requested_count,
            )

    job.processed_count = processed
    job.succeeded_count = succeeded
    job.set_skipped(skipped)
    job.status = BulkAsyncJob.Status.COMPLETE
    job.completed_at = datetime.now(tz=UTC)
    job.save()


def create_bulk_form_job(domain, action, requested_by, form_ids, api_key=None):
    """Use ``AtomicBlobs`` to prevent an orphaned requested ids blob"""
    with AtomicBlobs(get_blob_db()) as db:
        job = BulkAsyncJob(
            domain=domain,
            model=XFormInstance,
            action=action,
            requested_by=requested_by,
            api_key=api_key,
        )
        job.set_requested_ids(form_ids, db=db)
        job.save()
    return job


def build_form_action(job, user_id):
    """Return the per-form action callable for ``job.action``."""
    if job.action == BulkAsyncJob.Action.ARCHIVE:
        return partial(archive_forms, user_id=user_id)
    if job.action == BulkAsyncJob.Action.UNARCHIVE:
        return partial(unarchive_forms, user_id=user_id)
    raise BulkFormActionError(f'unknown bulk action: {job.action}')


def archive_forms(forms, user_id):
    yield from _apply_to_each(forms, lambda f: f.archive(user_id=user_id))


def unarchive_forms(forms, user_id):
    yield from _apply_to_each(forms, lambda f: f.unarchive(user_id=user_id))


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


def _apply_form_action(domain, form_ids, action_fn):
    """Apply ``action_fn`` to each batch of forms, yielding a result per id"""
    unresolved_ids = set(form_ids)
    all_forms = XFormInstance.objects.iter_forms(form_ids)
    # iter_forms returns one form at a time, but an action takes a batch
    for batch in chunked(all_forms, MAX_SAVE_INTERVAL):
        forms = []
        for form in batch:
            if form.domain == domain:
                forms.append(form)
                unresolved_ids.discard(form.form_id)
        yield from action_fn(forms)
    for form_id in unresolved_ids:
        yield FormActionResult(form_id, SKIPPED, NOT_FOUND)


def _apply_to_each(forms, apply_to_form):
    """Apply ``apply_to_form`` to each form, yielding its result."""
    for xform in forms:
        try:
            apply_to_form(xform)
        except Exception:
            notify_exception(None, "Error applying bulk form action", {
                'domain': xform.domain,
                'form_id': xform.form_id,
            })
            yield FormActionResult(xform.form_id, SKIPPED, UNEXPECTED_ERROR)
        else:
            yield FormActionResult(xform.form_id, SUCCEEDED)


def _save_interval(requested_count):
    """Every 5% or MAX_SAVE_INTERVAL forms, whichever is lower"""
    return max(1, min(MAX_SAVE_INTERVAL, requested_count // 20))


def _resolve_user_id(username):
    user = CouchUser.get_by_username(username)
    if user is None:
        raise BulkFormActionError(f"bulk form action: user {username} not found")
    return user.user_id
