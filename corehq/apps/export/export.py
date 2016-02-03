# TODO: This file has a dumb name
import os
import tempfile

from corehq.apps.es import FormES, CaseES
from corehq.apps.export.models.new import CaseExportInstance, \
    FormExportInstance
from couchexport.export import FormattedRow
from couchexport.writers import PythonDictWriter


class _Writer(object):
    """
    An object that provides a friendlier interface to couchexport.ExportWriters.
    """
    def __init__(self, writer):
        # An instance of a couchexport.ExportWriter
        self.writer = writer

    def open(self, file, tables):
        headers = [(t.identifier, (t.get_headers(),)) for t in tables]
        table_titles = {t.identifier: t.name for t in tables}
        return self.writer.open(headers, file, table_titles=table_titles)

    def write(self, table, row):
        return self.writer.write([(table.identifier, [FormattedRow(data=row.data)])])

    def close(self):
        return self.writer.close()

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

    writer = _Writer(PythonDictWriter())

    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'wb') as tmp:
        writer.open(tmp, export_instance.tables)

        for doc in documents:
            for table in export_instance.tables:
                rows = table.get_rows(doc)
                for row in rows:
                    # TODO: Maybe it is bad to write one row at a time when you can do more
                    # (from a performance perspective)
                    writer.write(table, row)
    writer.close()
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
