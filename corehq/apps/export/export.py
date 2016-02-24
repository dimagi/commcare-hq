import contextlib
import os
import tempfile

import datetime

from couchdbkit import ResourceConflict

from couchexport.groupexports import (
    _should_rebuild_export,
)
from soil import DownloadBase

from couchexport.export import FormattedRow, get_writer
from couchexport.files import Temp
from couchexport.models import Format
from corehq.apps.export.esaccessors import (
    get_form_export_base_query,
    get_case_export_base_query,
)
from corehq.apps.export.models.new import (
    CaseExportInstance,
    FormExportInstance,
    CachedExport,
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
    def open(self, tables):
        """
        Open the _Writer for writing. This must be called before using _Writer.write().
        Note that this function returns a context manager!
        A _Writer can only be opened once.
        """

        # Create and open a temp file
        assert self._path is None
        fd, self._path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as file:

            # open the ExportWriter
            headers = [(t, (t.get_headers(),)) for t in tables]
            table_titles = {t: t.label for t in tables}
            self.writer.open(headers, file, table_titles=table_titles)
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


def _get_tables(export_instances):
    """
    Return a list of tables for the given ExportInstances
    :param export_instances: A list of ExportInstances
    :return: a list of TableConfigurations
    """
    tables = []
    for export_instance in export_instances:
        tables.extend(export_instance.tables)
    return tables


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


def get_export_file(export_instances, filters):
    """
    Return an export file for the given ExportInstance and list of filters
    # TODO: Add a note about cleaning up the file?
    """

    writer = _get_writer(export_instances)
    with writer.open(_get_tables(export_instances)):
        for export_instance in export_instances:
            # TODO: Don't get the docs multiple times if you don't have to
            docs = _get_export_documents(export_instance, filters)
            _write_export_instance(writer, export_instance, docs)

    return ExportFile(writer.path, writer.format)


def _get_export_documents(export_instance, filters):
    query = _get_base_query(export_instance)
    for filter in filters:
        query = query.filter(filter.to_es_filter())
    return query.scroll()


def _write_export_instance(writer, export_instance, documents):
    """
    Write rows to the given open _Writer.
    Rows will be written to each table in the export instance for each of
    the given documents.
    :param writer: An open _Writer
    :param export_instance: An ExportInstance
    :param documents: A list of documents
    :return: None
    """

    for doc in documents:
        for table in export_instance.tables:
            rows = table.get_rows(doc)
            for row in rows:
                # It might be bad to write one row at a time when you can do more (from a performance perspective)
                # Regardless, we should handle the batching of rows in the _Writer class, not here.
                writer.write(table, row)


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
    saved_export = _get_cached_export_and_delete_copies(export_instance._id)
    if not _should_rebuild_export(saved_export, last_access_cutoff):
        return

    file = get_export_file([export_instance], filters or [])
    with file:
        _save_export_payload(export_instance._id, file, saved_export)


def _save_export_payload(export_instance_id, file, saved_export):
    """
    Save the contents of an export file to disk as part of the given saved export
    for later retrieval.
    """
    payload = file.file.payload

    if not saved_export:
        saved_export = CachedExport(export_instance_id=export_instance_id)

    if saved_export.last_accessed is None:
        saved_export.last_accessed = datetime.datetime.utcnow()
    saved_export.last_updated = datetime.datetime.utcnow()

    try:
        saved_export.save()
    except ResourceConflict:
        # task was executed concurrently, so let first to finish win and abort the rest
        pass
    else:
        saved_export.set_payload(payload)

def _get_cached_export_and_delete_copies(export_instance_id):

    matching = CachedExport.by_export_instance_id(export_instance_id)
    if not matching:
        return None
    if len(matching) == 1:
        return matching[0]
    else:
        # delete all matches besides the last updated match
        matching = sorted(matching, key=lambda x: x.last_updated)
        for match in matching[:-1]:
            match.delete()
        return matching[-1]
