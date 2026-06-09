from datetime import UTC, datetime

from django.db import models

from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.sql_db.models import PartitionedModel

SLUG_BY_MODEL = {
    CommCareCase: 'case',
    XFormInstance: 'xform',
}
MODEL_BY_SLUG = {token: model for model, token in SLUG_BY_MODEL.items()}


class ModelClassField(models.CharField):
    """Stores a slug in the DB but reads/writes Django model classes.

    Lets callers query and assign with the class itself, e.g.
    ``filter(model=XFormInstance)``.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 128)
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return MODEL_BY_SLUG[value]

    def to_python(self, value):
        if value is None or value in SLUG_BY_MODEL:
            return value
        return MODEL_BY_SLUG[value]

    def get_prep_value(self, value):
        if value is None or isinstance(value, str):
            return value
        return SLUG_BY_MODEL[value]


def build_tombstone(doc_type, doc_id, domain, deleted_on=None):
    return Tombstone(
        doc_id=doc_id,
        object_class_path=f'{doc_type.__module__}.{doc_type.__qualname__}',
        domain=domain,
        deleted_on=deleted_on or datetime.now(tz=UTC),
    )


class Tombstone(PartitionedModel):
    partition_attr = 'doc_id'

    doc_id = models.CharField(max_length=126)
    model = ModelClassField()
    domain = models.CharField(max_length=255)
    soft_deleted_on = models.DateTimeField(db_index=True)
    hard_deleted_on = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['doc_id', 'model'],
                name='tombstone_unique_id_and_model',
            )
        ]
