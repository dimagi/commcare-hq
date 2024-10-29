import json
from collections import namedtuple

from corehq.apps.export.models import ExportInstance
from corehq.util.metrics import metrics_histogram
from corehq.util.metrics.utils import bucket_value

FieldMetadata = namedtuple('FieldMetadata', ['name', 'odata_type'])


def get_case_odata_fields_from_config(case_export_config, table_id):
    # todo: this should eventually be handled by the data dictionary but we don't do a good
    # job of mapping that in exports today so we don't have datatype information handy.
    SPECIAL_TYPES = {
        'closed': 'Edm.Boolean',
        'modified_on': 'Edm.DateTimeOffset',
        'date_modified': 'Edm.DateTimeOffset',
        'server_modified_on': 'Edm.DateTimeOffset',
        'opened_on': 'Edm.DateTimeOffset',
    }
    return _get_odata_fields_from_columns(case_export_config, SPECIAL_TYPES, table_id)


def get_form_odata_fields_from_config(form_export_config, table_id):
    SPECIAL_TYPES = {
        'received_on': 'Edm.DateTimeOffset',
        'form.meta.timeStart': 'Edm.DateTimeOffset',
        'form.meta.timeEnd': 'Edm.DateTimeOffset',
    }
    return _get_odata_fields_from_columns(form_export_config, SPECIAL_TYPES, table_id)


def _get_odata_fields_from_columns(export_config, special_types, table_id):
    def _get_dot_path(export_column):
        if export_column and export_column.item and export_column.item.path:
            return '.'.join(subpath.name for subpath in export_column.item.path)
        return None

    if table_id + 1 > len(export_config.tables):
        return []

    table = export_config.tables[table_id]
    if not table.selected:
        return []

    metadata = []
    for column in table.selected_columns:
        for header in column.get_headers(split_column=export_config.split_multiselects):
            metadata.append(FieldMetadata(
                header,
                special_types.get(_get_dot_path(column), 'Edm.String')
            ))

    return metadata


def record_feed_access_in_datadog(request, config_id, duration, response):
    config = ExportInstance.get(config_id)
    json_response = json.loads(response.content.decode('utf-8'))
    rows = json_response['value']
    row_count = len(rows)
    try:
        column_count = len(rows[0])
    except IndexError:
        column_count = 0
    metrics_histogram(
        'commcare.odata_feed.test_v3', duration,
        bucket_tag='duration_bucket', buckets=(1, 5, 20, 60, 120, 300, 600), bucket_unit='s',
        tags={
            'domain': request.domain,
            'feed_type': config.type,
            'row_count': bucket_value(row_count, [100, 1000, 10000, 1000000]),
            'column_count': bucket_value(column_count, [10, 50, 100, 500, 1000]),
            'size': bucket_value(len(response.content) / (1024 ** 2), [1, 10, 100, 1000])  # in MB
        }
    )


def format_odata_error(code, message):
    error_message = {"error": {
        "code": code,
        "message": message,
    }}

    return error_message
