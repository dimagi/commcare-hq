import contextlib
import os
import tempfile

import datetime

from couchdbkit import ResourceConflict

from soil import DownloadBase

from couchexport.export import FormattedRow, get_writer
from couchexport.files import Temp
from couchexport.models import Format
from corehq.util.files import safe_filename
from corehq.apps.export.esaccessors import (
    get_form_export_base_query,
    get_case_export_base_query,
)
from corehq.apps.export.models.new import (
    CaseExportInstance,
    FormExportInstance,
)


class ExportFile(object):
    # This is essentially coppied from couchexport.files.ExportFiles

    def __init__(self, path, format):
        self.file = Temp(path)
        self.format = format

    def __enter__(self):
        return self.file.payload

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file.delete()


class _Writer(object):
    """
    An object that provides a friendlier interface to couchexport.ExportWriters.
    """

    def __init__(self, writer):
        # An instance of a couchexport.ExportWriter
        self.writer = writer
        self.format = writer.format
        self._path = None

    @contextlib.contextmanager
    def open(self, export_instances):
        """
        Open the _Writer for writing. This must be called before using _Writer.write().
        Note that this function returns a context manager!
        A _Writer can only be opened once.
        """

        # Create and open a temp file
        assert self._path is None

        if len(export_instances) == 1:
            name = export_instances[0].name or ''
        else:
            name = ''
        name = safe_filename(name)

        fd, self._path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as file:

            # open the ExportWriter
            headers = []
            table_titles = {}
            for instance in export_instances:
                headers += [
                    (t, (t.get_headers(split_columns=instance.split_multiselects),))
                    for t in instance.selected_tables
                ]
                table_titles.update({t: t.label for t in instance.selected_tables})
            self.writer.open(headers, file, table_titles=table_titles, archive_basepath=name)
            yield
            self.writer.close()

    def write(self, table, row):
        """
        Write the given row to the given table of the export.
        _Writer must be opened first.
        :param table: A TableConfiguration
        :param row: An ExportRow
        """
        return self.writer.write([(table, [FormattedRow(data=row.data)])])

    def get_preview(self):
        return self.writer.get_preview()

    @property
    def path(self):
        """
        The path to the file that this object writes to.
        """
        return self._path


def _get_writer(export_instances):
    """
    Return a new _Writer
    """
    format = Format.XLS_2007
    if len(export_instances) == 1:
        format = export_instances[0].export_format

    legacy_writer = get_writer(format)
    writer = _Writer(legacy_writer)
    return writer


def get_export_download(export_instances, filters, filename=None):
    from corehq.apps.export.tasks import populate_export_download_task

    download = DownloadBase()
    download.set_task(populate_export_download_task.delay(
        export_instances,
        filters,
        download.download_id,
        filename=filename
    ))
    return download


def get_export_file(export_instances, filters, progress_tracker=None):
    """
    Return an export file for the given ExportInstance and list of filters
    # TODO: Add a note about cleaning up the file?
    """

    writer = _get_writer(export_instances)
    with writer.open(export_instances):
        for export_instance in export_instances:
            # TODO: Don't get the docs multiple times if you don't have to
            docs = _get_export_documents(export_instance, filters)
            _write_export_instance(writer, export_instance, docs, progress_tracker)

    return ExportFile(writer.path, writer.format)


def _get_export_documents(export_instance, filters):
    query = _get_base_query(export_instance)
    for filter in filters:
        query = query.filter(filter.to_es_filter())
    # size here limits each scroll request, not the total number of results
    return query.size(1000).scroll()


def get_export_size(export_instance, filters):
    return _get_export_documents(export_instance, filters).count


def _write_export_instance(writer, export_instance, documents, progress_tracker=None):
    """
    Write rows to the given open _Writer.
    Rows will be written to each table in the export instance for each of
    the given documents.
    :param writer: An open _Writer
    :param export_instance: An ExportInstance
    :param documents: A ScanResult, or if progress_tracker is None, any iterable yielding documents
    :param progress_tracker: A task for soil to track progress against
    :return: None
    """
    if progress_tracker:
        DownloadBase.set_progress(progress_tracker, 0, documents.count)

    for row_number, doc in enumerate(documents):
        for table in export_instance.selected_tables:
            rows = table.get_rows(
                doc,
                row_number,
                split_columns=export_instance.split_multiselects,
                transform_dates=export_instance.transform_dates,
            )
            for row in rows:
                # It might be bad to write one row at a time when you can do more (from a performance perspective)
                # Regardless, we should handle the batching of rows in the _Writer class, not here.
                writer.write(table, row)
        if progress_tracker:
            DownloadBase.set_progress(progress_tracker, row_number + 1, documents.count)


def _get_base_query(export_instance):
    """
    Return an ESQuery object for the given export instance.
    Includes filters for domain, doc_type, and xmlns/case_type.
    """
    if isinstance(export_instance, FormExportInstance):
        return get_form_export_base_query(
            export_instance.domain,
            export_instance.app_id,
            export_instance.xmlns,
            export_instance.include_errors
        )
    if isinstance(export_instance, CaseExportInstance):
        return get_case_export_base_query(
            export_instance.domain, export_instance.case_type
        )
    else:
        raise Exception(
            "Unknown base query for export instance type {}".format(type(export_instance))
        )


def rebuild_export(export_instance, last_access_cutoff=None, filters=None):
    """
    Rebuild the given daily saved ExportInstance
    """
    if _should_not_rebuild_export(export_instance, last_access_cutoff):
        return

    file = get_export_file([export_instance], filters or [])
    with file as payload:
        _save_export_payload(export_instance, payload)


def _should_not_rebuild_export(export, last_access_cutoff):
    # Don't rebuild exports that haven't been accessed since last_access_cutoff
    return (
        last_access_cutoff
        and export.last_accessed
        and export.last_accessed < last_access_cutoff
    )


def _save_export_payload(export, payload):
    """
    Save the contents of an export file to disk for later retrieval.
    """
    if export.last_accessed is None:
        export.last_accessed = datetime.datetime.utcnow()
    export.last_updated = datetime.datetime.utcnow()

    try:
        export.save()
    except ResourceConflict:
        # task was executed concurrently, so let first to finish win and abort the rest
        pass
    else:
        export.set_payload(payload)
