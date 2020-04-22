from uuid import uuid4

from django.db import models
from django.utils.functional import cached_property

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.blobs import get_blob_db, CODES


class IncrementalExport(models.Model):
    domain = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    export_instance_id = models.CharField(max_length=126, db_index=True)
    connection_settings = models.ForeignKey('motech.ConnectionSettings', on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    def checkpoint(self, doc_id, doc_date):
        return IncrementalExportCheckpoint.objects.create(
            incremental_export=self,
            last_doc_id=doc_id,
            last_doc_date=doc_date
        )

    @property
    def export_instance(self):
        return get_properly_wrapped_export_instance(self.export_id)

    @cached_property
    def last_valid_checkpoint(self):
        for checkpoint in self.checkpoints.order_by('-date_created'):
            if checkpoint.blob_exists:
                return checkpoint


class IncrementalExportCheckpoint(models.Model):
    incremental_export = models.ForeignKey(IncrementalExport, related_name='checkpoints', on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    last_doc_id = models.CharField(max_length=126)
    last_doc_date = models.DateTimeField()
    blob_key = models.UUIDField(default=uuid4)

    def get_blob(self):
        db = get_blob_db()
        return db.get(key=self.blob_key, type_code=CODES.data_export)

    @property
    def blob_exists(self):
        db = get_blob_db()
        return db.exists(self.blob_key)
