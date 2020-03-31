from corehq.apps.export.det.base import DETRow, DETTable, DETConfig
from corehq.apps.export.det.helpers import collapse_path, collapse_path_out, truncate, prepend_prefix
from corehq.apps.export.models import FormExportInstance

PROPERTIES_PREFIX = 'properties.'
ACTIONS_PREFIX = 'actions.'
PREFIX_MAP = {
    0: PROPERTIES_PREFIX,
    1: '',
    2: ACTIONS_PREFIX,
}


def _get_default_case_rows():
    return [
        DETRow(source_field=row[0], field=row[1], map_via=row[2] if len(row) > 2 else '')
        for row in [
            ['id', 'id', ''],  # Case ID
            ['properties.case_type', 'properties.case_type'],  # Case Type
            ['properties.owner_id', 'properties.owner_id'],  # Owner ID
            ['properties.case_name', 'properties.case_name'],  # Case Name
            ['properties.date_opened', 'properties.date_opened', 'str2date'],  # Date opened(phone time)
            ['server_opened_on', 'server_opened_on', 'str2date'],  # Date opened(server time)
            ['opened_by', 'opened_by'],  # Opened by(user ID)
            ['closed', 'closed'],  # Is Closed
            ['date_closed', 'date_closed', 'str2date'],  # Date closed
            ['date_modified', 'date_modified', 'str2date'],  # Modified on(phone time)
            ['server_date_modified', 'server_date_modified', 'str2date'],  # Modified on(server time)
            ['indices.parent.case_id', 'indices.parent.case_id'],  # Parent case ID
            ['indices.parent.case_type', 'indices.parent.case_type'],  # Parent case type
        ]
    ]


def generate_case_schema(export_schema_json, main_sheet_name, output_file):
    main_table = DETTable(
        name=main_sheet_name,
        source='case',
        filter_name='type',
        filter_value=export_schema_json['case_type'],
        rows=_get_default_case_rows()
    )
    output = DETConfig(name=main_sheet_name, tables=[main_table])
    _add_schemas_to_output(output, export_schema_json)
    output.export_to_file(output_file)


def _get_default_form_rows():
    return [
        DETRow(source_field=row[0], field=row[1], map_via=row[2] if len(row) > 2 else '')
        for row in [
            ['id', 'id', ''],
            ['received_on', 'received_on', 'str2date'],
            ['xmlns', 'xmlns'],
            ['form.@name', 'form.@name'],
            ['app_id', 'app_id'],
            ['build_id', 'build_id'],
            ['form.@version', 'form.@version'],
            ['doc_type', 'doc_type'],
            ['last_sync_token', 'last_sync_token'],
            ['partial_submission', 'partial_submission'],
            ['edited_on', 'edited_on'],
            ['submit_ip', 'submit_ip'],
            ['form.meta.instanceID', 'instanceID'],
            ['form.meta.timeEnd', 'timeEnd', 'str2date'],
            ['form.meta.timeStart', 'timeStart', 'str2date'],
            ['form.meta.username', 'username'],
            ['form.meta.userID', 'userID'],
            ['form.meta.deviceID', 'deviceID'],
        ]
    ]


def generate_form_schema(export_schema_json, main_sheet_name, output_file):
    main_table = DETTable(
        name=main_sheet_name,
        source='form',
        filter_name='xmlns',
        filter_value=export_schema_json['xmlns'],
        rows=_get_default_form_rows()
    )
    output = DETConfig(name=main_sheet_name, tables=[main_table])
    _add_schemas_to_output(output, export_schema_json)
    output.export_to_file(output_file)


def _add_schemas_to_output(output, data):

    for i, form in enumerate(data['group_schemas']):
        header = output.name
        parent = collapse_path(form['path'])
        if parent:
            # header = header + '_' + parent
            tbl_name = parent.replace('[*]', '')
            if tbl_name.startswith('form.'):
                header = header + '_' + tbl_name[len('form.'):]
            else:
                header = header + '_' + tbl_name

        if header not in output.table_names:
            output.tables.append(
                DETTable(
                    name=header,
                    source=parent,
                    rows=[
                        DETRow(source_field='$.id', field='id')
                    ]

                )
            )

        current_table = output.get_table(header)
        default_prefix = PREFIX_MAP[i]
        for q in form['items']:

            path = collapse_path_out(q['path'], parent)
            prefixed_path = prepend_prefix(path, default_prefix)
            # x = _truncate(_collapse_path_src(q['path'], ''), 0, 63)
            x = truncate(path, 0, 63)

            # HACK: the ones using name are an attempt to capture dates
            # that have string as a datatype
            map_via = ''
            if q['datatype'] in ['integer']:
                map_via = 'str2num'

            if q['datatype'] in ['date', 'time'] or \
                    q['path'][-1]['name'] in ['add', 'edd', 'date', '@date', 'dob'] or \
                    q['path'][-1]['name'].endswith('_date') or \
                    q['path'][-1]['name'].startswith('date_') or \
                    q['path'][-1]['name'].startswith('@date_') or \
                    q['path'][-1]['name'].endswith('_dob') or \
                    q['path'][-1]['name'].startswith('dob_'):
                map_via = 'str2date'

            current_table.rows.append(DETRow(source_field=prefixed_path, field=x, map_via=map_via))


def generate_from_form_export_instance(export_instance, output_file):
    assert isinstance(export_instance, FormExportInstance)
    main_input_table = export_instance.selected_tables[0]
    main_output_table = DETTable(
        name=main_input_table.label,
        source='form',
        filter_name='xmlns',
        filter_value=export_instance.xmlns,
        rows=[],
    )
    output = DETConfig(name=export_instance.name, tables=[main_output_table])
    _add_rows_for_table(main_input_table, main_output_table)
    # todo: add rows for other tables
    output.export_to_file(output_file)


def _add_rows_for_table(input_table, output_table):
    for column in input_table.selected_columns:
        det_row = _get_det_row_for_export_column(column)
        output_table.rows.append(det_row)


def _get_det_row_for_export_column(column):
    return DETRow(
        source_field=column.item.readable_path,
        field=column.label,
    )
