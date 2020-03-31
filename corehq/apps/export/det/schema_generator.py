from corehq.apps.export.det.base import DETRow, DETTable, DETConfig
from corehq.apps.export.det.helpers import collapse_path, collapse_path_out, truncate, prepend_prefix

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
    data = export_schema_json

    main_table = DETTable(
        name=main_sheet_name,
        source='case',
        filter_name='type',
        filter_value=data['case_type'],
        rows=_get_default_case_rows()
    )
    output = DETConfig(name=main_sheet_name, tables=[main_table])
    _add_schemas_to_output(output, export_schema_json)
    output.export_to_file(output_file)


def _add_schemas_to_output(output, data):
    for i, form in enumerate(data['group_schemas']):
        header = output.name
        parent = collapse_path(form['path'])
        default_prefix = PREFIX_MAP[i]
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
                        DETRow(source_field='id', field='id')
                    ]

                )
            )

        current_table = output.get_table(header)
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
