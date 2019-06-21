from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import contextlib
import time
import sys
from collections import Counter

import datetime

from couchdbkit import ResourceConflict

from dimagi.utils.logging import notify_exception
from soil import DownloadBase

from couchexport.export import FormattedRow, get_writer
from couchexport.models import Format

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.elastic import iter_es_docs_from_query
from corehq.toggles import PAGINATED_EXPORTS
from corehq.util.files import safe_filename, TransientTempfile
from corehq.util.datadog.gauges import datadog_histogram, datadog_track_errors
from corehq.util.datadog.utils import load_counter, DAY_SCALE_TIME_BUCKETS
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
import six
from io import open


class ExportFile(object):
    # This is essentially coppied from couchexport.files.ExportFiles

    def __init__(self, path, format):
        self.path = path
        self.format = format

    def __enter__(self):
        self.file = open(self.path, 'rb')
        return self.file

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file.close()


class _ExportWriter(object):
    """
    An object that provides a friendlier interface to couchexport.ExportWriters.
    """

    def __init__(self, writer, temp_path):
        # An instance of a couchexport.ExportWriter
        self.writer = writer
        self.format = writer.format
        self.path = temp_path

    @contextlib.contextmanager
    def open(self, export_instances):
        """
        Open the _Writer for writing. This must be called before using _Writer.write().
        Note that this function returns a context manager!
        A _Writer can only be opened once.
        """

        if len(export_instances) == 1:
            name = export_instances[0].name or ''
        else:
            name = ''
        name = safe_filename(name)
        all_sheet_names = Counter(
            table.label for instance in export_instances for table in instance.selected_tables
        )

        with open(self.path, 'wb') as file:

            # open the ExportWriter
            headers = []
            table_titles = {}
            for instance_index, instance in enumerate(export_instances):
                headers += [
                    (t, (t.get_headers(split_columns=instance.split_multiselects),))
                    for t in instance.selected_tables
                ]
                for table_index, table in enumerate(instance.selected_tables):
                    sheet_name = table.label or "Sheet{}".format(table_index + 1)
                    # If it's a bulk export and the sheet has the same name as another sheet,
                    # Prefix the sheet name with the export name
                    if len(export_instances) > 1 and all_sheet_names[sheet_name] > 1:
                        sheet_name = "{}-{}".format(
                            instance.name or "Export{}".format(instance_index + 1),
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
        return self.writer.write([
            (table, [FormattedRow(data=row.data, hyperlink_column_indices=row.hyperlink_column_indices)])
        ])

    def get_preview(self):
        return self.writer.get_preview()


class _PaginatedExportWriter(object):

    def __init__(self, writer, temp_path):
        self.format = writer.format
        self.path = temp_path
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

        self.name = self._get_name(export_instances)
        self.headers = self._get_headers(export_instances)
        self.table_names = self._get_table_names(export_instances)

        with open(self.path, 'wb') as file_handle:
            self.writer.open(
                six.iteritems(self._get_paginated_headers()),
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
                    table_name = "{}-{}".format(
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
        return {self._paged_table_index(table): (headers,) for table, headers in six.iteritems(self.headers)}

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
        for table, table_name in six.iteritems(self.table_names):
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
        if self.rows_written[table] >= MAX_EXPORTABLE_ROWS * (self.pages[table] + 1):
            self.pages[table] += 1
            self.writer.add_table(
                self._paged_table_index(table),
                self._get_paginated_headers()[self._paged_table_index(table)][0],
                table_title=self._get_paginated_table_titles()[self._paged_table_index(table)],
            )

        self.writer.write([(self._paged_table_index(table), [FormattedRow(data=row.data)])])
        self.rows_written[table] += 1


def get_export_writer(export_instances, temp_path, allow_pagination=True):
    """
    Return a new _Writer
    """
    format = Format.XLS_2007
    if len(export_instances) == 1:
        format = export_instances[0].export_format

    legacy_writer = get_writer(format)
    if allow_pagination and PAGINATED_EXPORTS.enabled(export_instances[0].domain):
        writer = _PaginatedExportWriter(legacy_writer, temp_path)
    else:
        writer = _ExportWriter(legacy_writer, temp_path)
    return writer


def get_export_download(domain, export_ids, exports_type, username, filters, filename=None):
    from corehq.apps.export.tasks import populate_export_download_task

    download = DownloadBase()
    download.set_task(populate_export_download_task.delay(
        domain,
        export_ids,
        exports_type,
        username,
        filters,
        download.download_id,
        filename=filename
    ))
    return download


def get_export_file(export_instances, filters, temp_path, progress_tracker=None):
    """
    Return an export file for the given ExportInstance and list of filters
    """
    writer = get_export_writer(export_instances, temp_path)
    with writer.open(export_instances):
        for export_instance in export_instances:
            docs = get_export_documents(export_instance, filters)
            write_export_instance(writer, export_instance, docs, progress_tracker)

    return ExportFile(writer.path, writer.format)


def get_export_documents(export_instance, filters):
    # Pull doc ids from elasticsearch and stream to disk
    query = _get_export_query(export_instance, filters)
    return iter_es_docs_from_query(query)


def _get_export_query(export_instance, filters):
    query = _get_base_query(export_instance)
    for filter in filters:
        query = query.filter(filter.to_es_filter())
    return query


def get_export_size(export_instance, filters):
    return _get_export_query(export_instance, filters).count()


def write_export_instance(writer, export_instance, documents, progress_tracker=None):
    """
    Write rows to the given open _Writer.
    Rows will be written to each table in the export instance for each of
    the given documents.
    :param writer: An open _Writer
    :param export_instance: An ExportInstance
    :param documents: An iterable yielding documents
    :param progress_tracker: A task for soil to track progress against
    :return: None
    """
    if progress_tracker:
        DownloadBase.set_progress(progress_tracker, 0, documents.count)

    start = _time_in_milliseconds()
    total_bytes = 0
    total_rows = 0
    compute_total = 0
    write_total = 0
    track_load = load_counter(export_instance.type, "export", export_instance.domain)

    for row_number, doc in enumerate(documents):
        total_bytes += sys.getsizeof(doc)
        for table in export_instance.selected_tables:
            compute_start = _time_in_milliseconds()
            try:
                rows = table.get_rows(
                    doc,
                    row_number,
                    split_columns=export_instance.split_multiselects,
                    transform_dates=export_instance.transform_dates,
                )
            except Exception as e:
                notify_exception(None, "Error exporting doc", details={
                    'domain': export_instance.domain,
                    'export_instance_id': export_instance.get_id,
                    'export_table': table.label,
                    'doc_id': doc.get('_id'),
                })
                e.sentry_capture = False
                raise
            compute_total += _time_in_milliseconds() - compute_start

            write_start = _time_in_milliseconds()
            for row in rows:
                # It might be bad to write one row at a time when you can do more (from a performance perspective)
                # Regardless, we should handle the batching of rows in the _Writer class, not here.
                writer.write(table, row)
            write_total += _time_in_milliseconds() - write_start

            total_rows += len(rows)

        track_load()
        if progress_tracker:
            DownloadBase.set_progress(progress_tracker, row_number + 1, documents.count)

    end = _time_in_milliseconds()
    tags = ['format:{}'.format(writer.format)]
    _record_datadog_export_write_rows(write_total, total_bytes, total_rows, tags)
    _record_datadog_export_compute_rows(compute_total, total_bytes, total_rows, tags)
    _record_datadog_export_duration(end - start, total_bytes, total_rows, tags)
    _record_export_duration(end - start, export_instance)


def _time_in_milliseconds():
    return int(time.time() * 1000)


def _record_datadog_export_compute_rows(duration, doc_bytes, n_rows, tags):
    __record_datadog_export(duration, doc_bytes, n_rows, 'commcare.compute_export_rows_duration', tags)


def _record_datadog_export_write_rows(duration, doc_bytes, n_rows, tags):
    __record_datadog_export(duration, doc_bytes, n_rows, 'commcare.write_export_rows_duration', tags)


def _record_datadog_export_duration(duration, doc_bytes, n_rows, tags):
    __record_datadog_export(duration, doc_bytes, n_rows, 'commcare.export_duration', tags)


def __record_datadog_export(duration, doc_bytes, n_rows, metric, tags):
    # deprecated: datadog histograms used this way are usually meaningless
    # because they are aggregated on a 10s window (so unless you're constantly
    # processing at least 100 measurements per 10s window then the percentile
    # will approximate the average). Also more nuanced reasons. See
    # https://confluence.dimagi.com/x/4ArDAQ#TroubleshootingPasteboard/HQchatdumpingground-Datadog
    datadog_histogram(metric, duration, tags=tags)
    if doc_bytes:
        datadog_histogram(
            '{}_normalized_by_size'.format(metric),
            duration // doc_bytes,
            tags=tags,
        )
    if n_rows:
        datadog_histogram(
            '{}_normalized_by_rows'.format(metric),
            duration // n_rows,
            tags=tags,
        )


def _record_export_duration(duration, export):
    export.last_build_duration = duration
    try:
        export.save()
    except ResourceConflict:
        export = get_properly_wrapped_export_instance(export.get_id)
        export.last_build_duration = duration
        export.save()


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


@datadog_track_errors('rebuild_export', duration_buckets=DAY_SCALE_TIME_BUCKETS)
def rebuild_export(export_instance, progress_tracker):
    """
    Rebuild the given daily saved ExportInstance
    """
    filters = export_instance.get_filters()
    with TransientTempfile() as temp_path:
        export_file = get_export_file([export_instance], filters or [], temp_path, progress_tracker)
        with export_file as payload:
            save_export_payload(export_instance, payload)


def save_export_payload(export, payload):
    """
    Save the contents of an export file to disk for later retrieval.
    """
    if export.last_accessed is None:
        export.last_accessed = datetime.datetime.utcnow()
    export.last_updated = datetime.datetime.utcnow()

    try:
        with export.atomic_blobs():
            export.set_payload(payload)
    except ResourceConflict:
        # task was executed concurrently, so let first to finish win and abort the rest
        pass
