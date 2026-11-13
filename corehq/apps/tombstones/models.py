from datetime import UTC, datetime

from django.db import models

from corehq.sql_db.fields import ModelClassField
from corehq.sql_db.models import PartitionedModel


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
