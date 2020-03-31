from couchexport.export import export_raw
from couchexport.models import Format

PROPERTIES_PREFIX = 'properties.'
ACTIONS_PREFIX = 'actions.'
PREFIX_MAP = {
    0: PROPERTIES_PREFIX,
    1: '',
    2: ACTIONS_PREFIX,
}


def generate_case_schema(export_schema_json, main_sheet_name, output_file):
    data = export_schema_json

    TITLE_ROW = [
        'Source Field',
        'Field',
        'Map Via',
        'Data Source',
        'Filter Name',
        'Filter Value',
        'Table Name',
        'Format Via',
    ]

    output = {
        main_sheet_name: [
            # Case ID
            ['id', 'id', '', 'case', 'type', data['case_type']],
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
    }

    def _collapse_path_out(path, relative=''):
        return _collapse_path(path, relative, 0)

    def _prepend_prefix(path, default_prefix):
        if not path.startswith(default_prefix):
            return '{}{}'.format(default_prefix, path)
        return path


    # def _collapse_path_src(path, relative=''):
    #     return _collapse_path(path, relative, 1)
    # def _collapse_path(path, relative='', s=0):
    #     if relative:
    #         return '.'.join([p['name'] for p in path[s:]]).replace(relative+'.','',1)
    #     return '.'.join([p['name'] for p in path[s:]])

    def _collapse_path(path, relative='', s=0):
        if relative:
            return '.'.join(
                [
                    p['name'] + '[*]' if p['is_repeat'] else p['name'] for p in path[s:]
                ]).replace(relative + '.', '', 1)
        return '.'.join(
            [
                p['name'] + '[*]' if p['is_repeat'] else p['name'] for p in path[s:]
            ])

    def _truncate(name, start_char, total_char):
        if len(name) > total_char:
            name = name[:start_char] + '$' + name[-(total_char - (start_char + 1)):]
        return name

    for i, form in enumerate(data['group_schemas']):
        header = main_sheet_name
        parent = _collapse_path(form['path'])
        default_prefix = PREFIX_MAP[i]
        if parent:
            # header = header + '_' + parent
            tbl_name = parent.replace('[*]', '')
            if tbl_name.startswith('form.'):
                header = header + '_' + tbl_name[len('form.'):]
            else:
                header = header + '_' + tbl_name

        # Excel limits the length of worksheet names
        ws_name = _truncate(header, 3, 31)
        # worksheet = workbook.create_sheet(ws_name)
        ws_data = []

        if header not in output.keys():
            # PG has 64 character limit on table names
            table_name = _truncate(header, 3, 63)
            output[header] = [
                ['id', 'id', '', 'case', 'type', parent, table_name],
            ]

        for q in form['items']:

            path = _collapse_path_out(q['path'], parent)
            prefixed_path = _prepend_prefix(path, default_prefix)
            # x = _truncate(_collapse_path_src(q['path'], ''), 0, 63)
            x = _truncate(path, 0, 63)

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

            output[header].append([prefixed_path, x, map_via])

    header_sheets = []
    data_sheets = []
    for k, v in output.items():
        header_sheets.append((k, TITLE_ROW))
        data_sheets.append((k, output[k]))

    export_raw(header_sheets, data_sheets, output_file, format=Format.XLS_2007)
