"""The labels the last AI translation run of an app language couldn't
translate, kept for a day in the blob db so the Languages page can list
them when asked. The blob db, not the cache, because a full cache evicts
a list nobody has opened yet."""
import json
from datetime import datetime, timezone
from io import BytesIO

from corehq.blobs import CODES, get_blob_db
from corehq.blobs.models import BlobMeta

FAILED_LABELS_TIMEOUT = 24 * 60  # minutes


def save_failed_labels(domain, app_id, lang, records):
    """Replace the language's list with this run's. An empty list only
    removes the previous run's."""
    db = get_blob_db()
    old = [
        meta for meta in db.metadb.get_for_parent(app_id, CODES.ai_translation_failed_labels)
        if meta.name == lang
    ]
    if old:
        db.bulk_delete(metas=old)
    if not records:
        return
    db.put(
        BytesIO(json.dumps(records).encode('utf-8')),
        domain=domain,
        parent_id=app_id,
        type_code=CODES.ai_translation_failed_labels,
        name=lang,
        timeout=FAILED_LABELS_TIMEOUT,
    )


def get_failed_labels(app_id, lang):
    """The last run's list, or None if the run was over a day ago or left
    nothing untranslated."""
    db = get_blob_db()
    try:
        meta = db.metadb.get(parent_id=app_id, type_code=CODES.ai_translation_failed_labels,
                             name=lang)
    except BlobMeta.DoesNotExist:
        return None
    # an expired blob stays readable until the cleanup task deletes it;
    # expires_on is naive UTC, as USE_TZ is off
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if meta.expires_on and meta.expires_on < now:
        return None
    with db.get(meta=meta) as stream:
        return json.load(stream)
