"""Blob payload helpers for BulkAsyncJob requested/skipped id lists."""
import json
from io import BytesIO

from corehq.blobs import CODES, get_blob_db


def save_requested_ids(domain, parent_id, form_ids):
    """Store the requested ids payload; returns the blob key."""
    return _put(domain, parent_id, {"requested_ids": list(form_ids)})


def read_requested_ids(key):
    return _get(key)["requested_ids"]


def save_skipped_ids(domain, parent_id, skipped):
    """Store the skipped ids payload (list of {"id", "reason"}); returns the blob key."""
    return _put(domain, parent_id, list(skipped))


def read_skipped_ids(key):
    return _get(key)


def _put(domain, parent_id, payload):
    content = BytesIO(json.dumps(payload).encode('utf-8'))
    meta = get_blob_db().put(
        content,
        domain=domain,
        parent_id=parent_id,
        type_code=CODES.bulk_async_job,
    )
    return meta.key


def _get(key):
    with get_blob_db().get(key=key, type_code=CODES.bulk_async_job) as fileobj:
        return json.load(fileobj)
