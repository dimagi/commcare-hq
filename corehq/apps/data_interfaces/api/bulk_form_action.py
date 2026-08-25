from dimagi.utils.parsing import json_format_datetime

from corehq.apps.data_interfaces.models import BulkAsyncJob

MAX_FORM_IDS = 5000

ALLOWED_ACTIONS = (
    BulkAsyncJob.Action.ARCHIVE,
    BulkAsyncJob.Action.UNARCHIVE,
)


class UserError(Exception):
    """A bad request. Rendered as a 400 by the view layer."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


def validate_payload(data):
    """Validate a bulk form action request body.

    :param data: the deserialized JSON request body
    :returns: an ``(action, form_ids)`` tuple
    :raises UserError: if the body is not valid
    """
    if not isinstance(data, dict):
        raise UserError("Payload must be a single JSON object")

    action = data.get('action')
    if not isinstance(action, str) or action not in ALLOWED_ACTIONS:
        raise UserError(f"'action' must be one of: {', '.join(ALLOWED_ACTIONS)}")

    form_ids = data.get('form_ids')
    if not isinstance(form_ids, list) or not form_ids:
        raise UserError("'form_ids' must be a non-empty list of form ids")
    if not all(isinstance(form_id, str) and form_id for form_id in form_ids):
        raise UserError("'form_ids' must contain only non-empty strings")
    if len(form_ids) > MAX_FORM_IDS:
        raise UserError(
            f"You cannot submit more than {MAX_FORM_IDS} form ids in a single request"
        )

    return action, form_ids


def serialize_job(job):
    """Return the public JSON representation of ``job``"""
    return {
        'id': job.id.hex,
        'action': job.action,
        'status': job.status,
        'requested_by': job.requested_by,
        'requested': job.requested_count,
        'processed': job.processed_count,
        'succeeded': job.succeeded_count,
        'skipped': job.get_skipped() if job.is_done and job.skipped_ids_blob_key else {},
        'created_at': json_format_datetime(job.created_at),
        'started_at': json_format_datetime(job.started_at) if job.started_at else None,
        'completed_at': json_format_datetime(job.completed_at) if job.completed_at else None,
    }
