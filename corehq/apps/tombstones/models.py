from datetime import UTC, datetime

from django.db import models

from corehq.sql_db.models import PartitionedModel, RequireDBManager
from corehq.sql_db.util import split_list_by_db_partition


def create_tombstone_for_form(form):
    from corehq.form_processor.models.forms import XFormInstance

    return Tombstone(
        doc_id=form.form_id,
        object_class_path=f'{XFormInstance.__module__}.{XFormInstance.__qualname__}',
        domain=form.domain,
        deleted_on=form.deleted_on or datetime.now(tz=UTC),
    )


class TombstoneObjectManager(RequireDBManager):
    def get_tombstones(self, doc_ids):
        tombstones = []
        for db_name, split_doc_ids in split_list_by_db_partition(doc_ids):
            tombstones.extend(
                self.using(db_name).filter(doc_id__in=split_doc_ids)
            )
        return tombstones


class Tombstone(PartitionedModel):
    partition_attr = 'doc_id'

    doc_id = models.CharField(max_length=126)
    object_class_path = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    deleted_on = models.DateTimeField(db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['doc_id', 'object_class_path'],
                name='tombstone_unique_id_and_type',
            )
        ]

    objects = TombstoneObjectManager()
