import contextlib
import os
import tempfile

from corehq.apps.es import FormES, CaseES
from corehq.apps.export.models.new import (
    CaseExportInstance,
    FormExportInstance,
)
from couchexport.export import FormattedRow, get_writer


class _Writer(object):
    """
    An object that provides a friendlier interface to couchexport.ExportWriters.
    """
    def __init__(self, writer):
        # An instance of a couchexport.ExportWriter
        self.writer = writer

    @contextlib.contextmanager
    def open(self, tables):
        """
        Open the _Writer for writing. This must be called before using _Writer.write()
        Note that this function returns a context manager!
        """

        # Create a nd open a temp file
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as file:

            # open the ExportWriter
            headers = [(t.identifier, (t.get_headers(),)) for t in tables]
            table_titles = {t.identifier: t.name for t in tables}
            self.writer.open(headers, file, table_titles=table_titles)
            yield

        self.writer.close()

    def write(self, table, row):
        return self.writer.write([(table.identifier, [FormattedRow(data=row.data)])])

    def get_preview(self):
        return self.writer.get_preview()


def get_export_file(export_instance, filters):
    """
    Return an export file for the given ExportInstance and list of filters
    """
    docs = _get_export_documents(export_instance, filters)
    return _write_export_file(export_instance, docs)


def _get_export_documents(export_instance, filters):
    query = _get_base_query(export_instance)
    for filter in filters:
        query = query.filter(filter.to_es_filter())
    result = query.run()
    return result.hits


def _write_export_file(export_instance, documents):

    legacy_writer = get_writer(export_instance.format)
    writer = _Writer(legacy_writer)

    with writer.open(export_instance.tables):
        for doc in documents:
            for table in export_instance.tables:
                rows = table.get_rows(doc)
                for row in rows:
                    # It might be bad to write one row at a time when you can do more (from a performance perspective)
                    # Regardless, we should handle the batching of rows in the _Writer class, not here.
                    writer.write(table, row)
    return writer.get_preview()


def _get_base_query(export_instance):
    """
    Return an ESQuery object for the given export instance.
    Includes filters for domain, doc_type, and xmlns/case_type.
    :param export_instance:
    :return:
    """
    if isinstance(export_instance, FormExportInstance):
        return _get_form_export_base_query(export_instance)
    if isinstance(export_instance, CaseExportInstance):
        return _get_case_export_base_query(export_instance)
    else:
        raise Exception("Unknown export instance type")


def _get_form_export_base_query(export_instance):
    return (FormES().
            domain(export_instance.domain)
            .xmlns(export_instance.xmlns)
            .sort("received_on"))
    # TODO: This probably needs app_id too


def _get_case_export_base_query(export_instance):
    return (CaseES()
            .domain(export_instance.domain)
            .case_type(export_instance.case_type)
            .sort("modified_on"))
