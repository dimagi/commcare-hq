from datetime import UTC, datetime

from django.db import models

from corehq.sql_db.models import PartitionedModel


class ModelClassField(models.CharField):
    """Stores a slug in the DB but reads/writes Django model classes.

    Lets callers query and assign with the class itself, e.g.
    ``filter(model=XFormInstance)``.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 128)
        super().__init__(*args, **kwargs)

    @property
    def _slug_by_model(self):
        from corehq.form_processor.models import CommCareCase, XFormInstance

        return {CommCareCase: 'case', XFormInstance: 'xform'}

    @property
    def _model_by_slug(self):
        return {v: k for k, v in self._slug_by_model.items()}

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return self._model_by_slug[value]

    def to_python(self, value):
        if value is None or value in self._slug_by_model:
            return value
        return self._model_by_slug[value]

    def get_prep_value(self, value):
        if value is None or isinstance(value, str):
            return value
        return self._slug_by_model[value]


def build_tombstone(
    model, doc_id, domain, soft_deleted_on=None, hard_deleted_on=None
):
    return Tombstone(
        doc_id=doc_id,
        model=model,
        domain=domain,
        soft_deleted_on=soft_deleted_on or datetime.now(tz=UTC),
        hard_deleted_on=hard_deleted_on or datetime.now(tz=UTC),
    )


class Tombstone(PartitionedModel):
    partition_attr = 'doc_id'

    doc_id = models.CharField(max_length=126)
    model = ModelClassField()
    domain = models.CharField(max_length=255)
    deletion_id = models.CharField(max_length=255, null=True)
    soft_deleted_on = models.DateTimeField(db_index=True)
    hard_deleted_on = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['doc_id', 'model'],
                name='tombstone_unique_id_and_model',
            )
        ]
