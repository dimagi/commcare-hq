import contextlib
import os
import tempfile
from collections import Counter

import datetime

from couchdbkit import ResourceConflict
from collections import Counter

from soil import DownloadBase

from couchexport.export import FormattedRow, get_writer
from couchexport.files import Temp
from couchexport.models import Format
from corehq.toggles import PAGINATED_EXPORTS
from corehq.util.files import safe_filename
from corehq.apps.export.esaccessors import (
    get_form_export_base_query,
    get_case_export_base_query,
    get_sms_export_base_query,
)
from corehq.apps.export.models.new import (
    CaseExportInstance,
    FormExportInstance,
    SMSExportInstance,
)
from corehq.apps.export.const import MAX_EXPORTABLE_ROWS


class ExportFile(object):
    # This is essentially coppied from couchexport.files.ExportFiles

    def __init__(self, path, format):
        self.file = Temp(path)
        self.format = format

    def __enter__(self):
        return self.file.file

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
        all_sheet_names = Counter(
            table.label for instance in export_instances for table in instance.selected_tables
        )

        fd, self._path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as file:

            # open the ExportWriter
            headers = []
            table_titles = {}
            for instance_index, instance in enumerate(export_instances):
                headers += [
                    (t, (t.get_headers(split_columns=instance.split_multiselects),))
                    for t in instance.selected_tables
                ]
                for table_index, table in enumerate(instance.selected_tables):
                    sheet_name = table.label or u"Sheet{}".format(table_index + 1)
                    # If it's a bulk export and the sheet has the same name as another sheet,
                    # Prefix the sheet name with the export name
                    if len(export_instances) > 1 and all_sheet_names[sheet_name] > 1:
                        sheet_name = u"{}-{}".format(
                            instance.name or u"Export{}".format(instance_index + 1),
                            sheet_name
                        )
                    table_titles[table] = sheet_name
            self.writer.open(headers, file, table_titles=table_titles, archive_basepath=name)
            try:
                yield
            finally:
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


class _PaginatedWriter(object):

    def __init__(self, writer, page_length=None):
        self.format = writer.format
        self._path = None
        self.page_length = page_length or MAX_EXPORTABLE_ROWS
        self.pages = Counter()
        self.rows_written = Counter()
        # An instance of a couchexport.ExportWriter
        self.writer = writer
        self.file_handle = None

    @contextlib.contextmanager
    def open(self, export_instances):
        """
        Open the _PaginatedWriter for writing. This must be called before using _PaginatedWriter.write().
        A _PaginatedWriter can only be opened once.
        """

        assert self._path is None

        self.name = self._get_name(export_instances)
        self.headers = self._get_headers(export_instances)
        self.table_names = self._get_table_names(export_instances)

        # Create and open a temp file
        fd, self._path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as file_handle:
            self.writer.open(
                self._get_paginated_headers().iteritems(),
                file_handle,
                table_titles=self._get_paginated_table_titles(),
                archive_basepath=self.name
            )
            try:
                yield
            finally:
                self.writer.close()

    def _get_name(self, export_instances):
        if len(export_instances) == 1:
            name = export_instances[0].name or 'Export'
        else:
            name = 'BulkExport'
        return safe_filename(name)

    def _get_headers(self, export_instances):
        '''
        Returns a dictionary that maps all TableConfigurations in the list of ExportInstances to an
        array of headers
        {
            TableConfiguration(): ['Column1', 'Column2']
            ...
        }

        :export_instances: - A list of ExportInstances
        '''
        headers = {}
        for instance_index, instance in enumerate(export_instances):
            for table in instance.selected_tables:
                headers[table] = table.get_headers(
                    split_columns=instance.split_multiselects
                )

        return headers

    def _get_table_names(self, export_instances):
        '''
        Returns a dictionary that maps all TableConfigurations in the list of ExportInstances to a
        table name. If the table name is a duplicate from another ExportInstance, it will automatically
        prefix the table name with the export name to prevent duplicate table names.

        {
            TableConfiguration(): 'Table Name'
        }
        '''
        table_names = {}
        for instance_index, instance in enumerate(export_instances):
            for table_index, table in enumerate(instance.selected_tables):
                table_name = table.label or "Sheet{}".format(table_index + 1)
                if len(export_instances) > 1:
                    table_name = u"{}-{}".format(
                        instance.name or "Export{}".format(instance_index + 1),
                        table_name
                    )
                table_names[table] = table_name
        return table_names

    def _paged_table_index(self, table):
        '''
        Returns an index of the paged table. Relies on the internal state of self.pages
        ((PathNode(), PathNode()), 3)
        '''
        return (tuple(table.path), self.pages[table])

    def _get_paginated_headers(self):
        '''
        Maps the headers in self.headers to
        1) Match the data structure that couchexport.writers.ExportWriter expects
        2) Map the key in the headers dictionary to the paged table index

        {
            TableConfiguration(): ['Column1', 'Column2']
        }

        Becomes

        {
            (<table.path>, <page>): (['Column1', 'Column2'],)
        }
        '''
        return {self._paged_table_index(table): (headers,) for table, headers in self.headers.iteritems()}

    def _get_paginated_table_titles(self):
        '''
        Maps the table titles to tables titles with their page count

        {
            TableConfiguration(): 'Table Name'
        }

        Becomes
        {
            (<table.path>, <page>: 'Table Name_<page>'
        }
        '''
        paginated_table_titles = {}
        for table, table_name in self.table_names.iteritems():
            paginated_table_titles[self._paged_table_index(table)] = '{}_{}'.format(
                table_name, format(self.pages[table], '03')
            )
        return paginated_table_titles

    def write(self, table, row):
        """
        Write the given row to the given table of the export.
        Will automatically open a new table and write to that if it
        has exceeded the number of rows written in the first table.
        :param table: A TableConfiguration
        :param row: An ExportRow
        """
        if self.rows_written[table] >= self.page_length * (self.pages[table] + 1):
            self.pages[table] += 1
            self.writer.add_table(
                self._paged_table_index(table),
                self._get_paginated_headers()[self._paged_table_index(table)][0],
                table_title=self._get_paginated_table_titles()[self._paged_table_index(table)],
            )

        self.writer.write([(self._paged_table_index(table), [FormattedRow(data=row.data)])])
        self.rows_written[table] += 1

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
    if PAGINATED_EXPORTS.enabled(export_instances[0].domain):
        writer = _PaginatedWriter(legacy_writer)
    else:
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
    # We believe we can occasionally hit the 5m limit to process a single scroll window
    # with a window size of 1000 (https://manage.dimagi.com/default.asp?248384).
    # Thus, smaller window size is intentional
    return query.size(500).scroll()


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
    if isinstance(export_instance, SMSExportInstance):
        return get_sms_export_base_query(export_instance.domain)
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
    filters = filters or export_instance.get_filters()
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
