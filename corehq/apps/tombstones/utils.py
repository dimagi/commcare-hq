from datetime import UTC, datetime

from corehq.apps.tombstones.models import Tombstone
from corehq.form_processor.models.forms import XFormInstance


def create_tombstone_for_form(form):
    return Tombstone(
        doc_id=form.form_id,
        object_class_path=f'{XFormInstance.__module__}.{XFormInstance.__qualname__}',
        domain=form.domain,
        deleted_on=form.deleted_on or datetime.now(tz=UTC),
    )
