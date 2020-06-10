from uuid import uuid4

from django.db import models

from couchexport.models import Format

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.export import (
    ExportFile,
    _get_export_query,
    get_export_writer,
    write_export_instance,
)
from corehq.apps.export.filters import ServerModifiedOnRangeFilter
from corehq.blobs import CODES, get_blob_db
from corehq.motech.models import RequestLog
from corehq.util.files import TransientTempfile
from corehq.util.metrics import metrics_track_errors


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


def generate_and_send_incremental_export(incremental_export, from_date):
    checkpoint = _generate_incremental_export(incremental_export, from_date)
    if checkpoint:
        _send_incremental_export(incremental_export, checkpoint)
    return checkpoint


def _generate_incremental_export(incremental_export, last_doc_date=None):
    export_instance = incremental_export.export_instance
    export_instance.export_format = Format.UNZIPPED_CSV  # force to unzipped CSV

    # Remove the date period from the ExportInstance, since this is added automatically by Daily Saved exports
    export_instance.filters.date_period = None
    filters = export_instance.get_filters()
    if last_doc_date:
        filters.append(ServerModifiedOnRangeFilter(gt=last_doc_date))

    class LastDocTracker:
        def __init__(self, doc_iterator):
            self.doc_iterator = doc_iterator
            self.last_doc = None
            self.doc_count = 0

        def __iter__(self):
            for doc in self.doc_iterator:
                self.last_doc = doc
                self.doc_count += 1
                yield doc

    with TransientTempfile() as temp_path, metrics_track_errors('generate_incremental_exports'):
        writer = get_export_writer([export_instance], temp_path, allow_pagination=False)
        with writer.open([export_instance]):
            query = _get_export_query(export_instance, filters)
            query = query.sort('server_modified_on')  # reset sort to this instead of opened_on
            docs = LastDocTracker(query.run().hits)
            write_export_instance(writer, export_instance, docs)

        export_file = ExportFile(writer.path, writer.format)

        if docs.doc_count <= 0:
            return

        new_checkpoint = incremental_export.checkpoint(
            docs.doc_count, docs.last_doc.get('server_modified_on')
        )

        with export_file as file_:
            db = get_blob_db()
            db.put(
                file_,
                domain=incremental_export.domain,
                parent_id=new_checkpoint.blob_parent_id,
                type_code=CODES.data_export,
                key=str(new_checkpoint.blob_key),
                timeout=24 * 60
            )
    return new_checkpoint


def _send_incremental_export(export, checkpoint):
    requests = _get_requests(checkpoint, export)
    headers = {
        'Accept': 'application/json'
    }
    files = {'file': (checkpoint.filename, checkpoint.get_blob(), 'text/csv')}
    requests.post(endpoint='', files=files, headers=headers)


def _get_requests(checkpoint, export):
    return export.connection_settings.get_requests(checkpoint.id, checkpoint.log_request)
