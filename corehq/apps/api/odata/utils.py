from __future__ import absolute_import, unicode_literals

import json
from collections import namedtuple

from corehq.apps.export.models import ExportInstance
from corehq.util.datadog.gauges import datadog_counter
from corehq.util.datadog.utils import bucket_value

FieldMetadata = namedtuple('FieldMetadata', ['name', 'odata_type'])


def get_case_odata_fields_from_config(case_export_config):
    # todo: this should eventually be handled by the data dictionary but we don't do a good
    # job of mapping that in exports today so we don't have datatype information handy.
    SPECIAL_TYPES = {
        'closed': 'Edm.Boolean',
        'modified_on': 'Edm.DateTimeOffset',
        'date_modified': 'Edm.DateTimeOffset',
        'server_modified_on': 'Edm.DateTimeOffset',
        'opened_on': 'Edm.DateTimeOffset',
    }
    return _get_odata_fields_from_columns(case_export_config, SPECIAL_TYPES)


def get_form_odata_fields_from_config(form_export_config):
    SPECIAL_TYPES = {
        'received_on': 'Edm.DateTimeOffset',
        'form.meta.timeStart': 'Edm.DateTimeOffset',
        'form.meta.timeEnd': 'Edm.DateTimeOffset',
    }
    return _get_odata_fields_from_columns(form_export_config, SPECIAL_TYPES)


def _get_odata_fields_from_columns(export_config, special_types):
    def _get_dot_path(export_column):
        if export_column and export_column.item and export_column.item.path:
            return '.'.join(subpath.name for subpath in export_column.item.path)
        return None

    return [FieldMetadata(column.label, special_types.get(_get_dot_path(column), 'Edm.String'))
            for column in export_config.tables[0].selected_columns]


def record_feed_access_in_datadog(request, config_id, duration, response):
    config = ExportInstance.get(config_id)
    username = request.couch_user.username
    json_response = json.loads(response.content.decode('utf-8'))
    rows = json_response['value']
    row_count = len(rows)
    try:
        column_count = len(rows[0])
    except IndexError:
        column_count = 0
    datadog_counter('commcare.odata_feed.test_v3', tags=[
        'domain:{}'.format(request.domain),
        'feed_id:{}'.format(config_id),
        'feed_type:{}'.format(config.type),
        'username:{}'.format(username),
        'row_count:{}'.format(row_count),
        'column_count:{}'.format(column_count),
        'size:{}'.format(len(response.content)),
        'duration:{}'.format(duration),
        'duration_bucket:{}'.format(bucket_value(duration, (1, 5, 20, 60, 120, 300, 600), 's')),
    ])
