from django.db import models


from corehq.sql_db.models import PartitionedModel


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
