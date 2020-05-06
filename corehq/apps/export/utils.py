from django.http import Http404

from couchdbkit import ResourceNotFound

from couchexport.models import Format

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.blobs import CODES, get_blob_db
from corehq.privileges import DAILY_SAVED_EXPORT, EXCEL_DASHBOARD
from corehq.toggles import MESSAGE_LOG_METADATA
from corehq.util.files import TransientTempfile
from corehq.util.metrics import metrics_track_errors

from .export import (
    ExportFile,
    _get_export_query,
    get_export_writer,
    write_export_instance,
)
from .filters import ServerModifiedOnRangeFilter


def is_occurrence_deleted(last_occurrences, app_ids_and_versions):
    is_deleted = True
    for app_id, version in app_ids_and_versions.items():
        occurrence = last_occurrences.get(app_id)
        if occurrence is not None and occurrence >= version:
            is_deleted = False
            break
    return is_deleted


def domain_has_excel_dashboard_access(domain):
    return domain_has_privilege(domain, EXCEL_DASHBOARD)


def domain_has_daily_saved_export_access(domain):
    return domain_has_privilege(domain, DAILY_SAVED_EXPORT)


def get_export(export_type, domain, export_id=None, username=None):
    from corehq.apps.export.models import (
        FormExportInstance,
        CaseExportInstance,
        SMSExportInstance,
        SMSExportDataSchema
    )
    if export_type == 'form':
        try:
            return FormExportInstance.get(export_id)
        except ResourceNotFound:
            raise Http404()
    elif export_type == 'case':
        try:
            return CaseExportInstance.get(export_id)
        except ResourceNotFound:
            raise Http404()
    elif export_type == 'sms':
        if not username:
            raise Exception("Username needed to ensure permissions")
        include_metadata = MESSAGE_LOG_METADATA.enabled(username)
        return SMSExportInstance._new_from_schema(
            SMSExportDataSchema.get_latest_export_schema(domain, include_metadata)
        )
    raise Exception("Unexpected export type received %s" % export_type)


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
    requests.post(uri='', files=files, headers=headers)


def _get_requests(checkpoint, export):
    return export.connection_settings.get_requests(checkpoint.id, checkpoint.log_request)
