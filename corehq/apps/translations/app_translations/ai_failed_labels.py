"""The labels the last AI translation run of an app language couldn't
translate, kept for a day in the blob db so the Languages page can list
them when asked. The blob db, not the cache, because a full cache evicts
a list nobody has opened yet."""
import json
from datetime import datetime, timezone
from io import BytesIO

from django.utils.translation import gettext as _

from corehq.apps.translations.app_translations.ai_status import (
    FINISHED_STATUS_TIMEOUT,
)
from corehq.apps.translations.app_translations.ai_translator import (
    PROBLEM_EMPTY,
    PROBLEM_FORMATTING_CHANGED,
    PROBLEM_INVALID_CHARACTERS,
    PROBLEM_LINK_CHANGED,
    PROBLEM_NO_TRANSLATION,
    PROBLEM_NOT_APPLIED,
    PROBLEM_OUTPUT_CHANGED,
)
from corehq.blobs import CODES, NotFound, get_blob_db
from corehq.blobs.models import BlobMeta

# minutes; the list lasts as long as the status that has its count
FAILED_LABELS_TIMEOUT = FINISHED_STATUS_TIMEOUT // 60
MAX_FAILED_LABELS = 1000


def save_failed_labels(domain, app_id, lang, records):
    """Replace the language's failed-label list with this run's.

    Only the first ``MAX_FAILED_LABELS`` labels are kept. An empty list
    only removes the previous run's.
    """
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
        BytesIO(json.dumps(records[:MAX_FAILED_LABELS]).encode('utf-8')),
        domain=domain,
        parent_id=app_id,
        type_code=CODES.ai_translation_failed_labels,
        name=lang,
        timeout=FAILED_LABELS_TIMEOUT,
    )


def failed_label_reason(code):
    return {
        PROBLEM_NO_TRANSLATION: _("The AI didn't return a translation."),
        PROBLEM_NOT_APPLIED: _("The app didn't accept the AI's translation."),
        PROBLEM_EMPTY: _("The AI returned an empty translation."),
        PROBLEM_INVALID_CHARACTERS: _("The AI's translation has characters the app can't save."),
        PROBLEM_OUTPUT_CHANGED: _("The AI changed or left out a value inserted from another question."),
        PROBLEM_FORMATTING_CHANGED: _("The AI changed the formatting, such as bold text or a list."),
        PROBLEM_LINK_CHANGED: _("The AI changed a web link."),
    }.get(code, _("The label couldn't be translated."))


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
    try:
        with db.get(meta=meta) as stream:
            return json.load(stream)
    except NotFound:
        # a newer run replaced the list after its metadata was read
        return None
