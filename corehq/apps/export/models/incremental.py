from uuid import uuid4

from django.db import models

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.blobs import CODES, get_blob_db
from corehq.motech.models import RequestLog


class IncrementalExport(models.Model):
    domain = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    export_instance_id = models.CharField(max_length=126, db_index=True)
    connection_settings = models.ForeignKey('motech.ConnectionSettings', on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    def checkpoint(self, doc_count, last_doc_date):
        return IncrementalExportCheckpoint.objects.create(
            incremental_export=self,
            doc_count=doc_count,
            last_doc_date=last_doc_date
        )

    @property
    def export_instance(self):
        return get_properly_wrapped_export_instance(self.export_instance_id)

    @property
    def last_valid_checkpoint(self):
        return self.checkpoints.filter(status=IncrementalExportStatus.SUCCESS).order_by('-date_created').first()


class IncrementalExportStatus(object):
    SUCCESS = 1
    FAILURE = 2
    CHOICES = (
        (SUCCESS, "success"),
        (FAILURE, "failure"),
    )

    @staticmethod
    def from_log_entry(entry):
        if entry.response_status in (200, 201):
            return IncrementalExportStatus.SUCCESS
        else:
            return IncrementalExportStatus.FAILURE


class IncrementalExportCheckpoint(models.Model):
    incremental_export = models.ForeignKey(IncrementalExport, related_name='checkpoints', on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    doc_count = models.IntegerField(null=True)
    last_doc_date = models.DateTimeField()
    blob_key = models.UUIDField(default=uuid4)

    status = models.PositiveSmallIntegerField(choices=IncrementalExportStatus.CHOICES, null=True)
    request_log = models.ForeignKey(RequestLog, on_delete=models.CASCADE, null=True)

    @property
    def blob_parent_id(self):
        return str(self.id)

    def get_blob(self):
        db = get_blob_db()
        return db.get(key=str(self.blob_key), type_code=CODES.data_export)

    def blob_exists(self):
        db = get_blob_db()
        return db.exists(key=str(self.blob_key))

    def log_request(self, log_level, log_entry):
        log = RequestLog.log(log_level, log_entry)
        self.status = IncrementalExportStatus.from_log_entry(log_entry)
        self.request_log = log
        self.save()

    @property
    def filename(self):
        date_suffix = self.date_created.replace(microsecond=0).strftime('%Y-%m-%d-%H-%M-%S')
        return f'{self.incremental_export.name}-{date_suffix}.csv'
