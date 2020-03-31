import attr

from couchexport.export import export_raw
from couchexport.models import Format

PROPERTIES_PREFIX = 'properties.'
ACTIONS_PREFIX = 'actions.'
PREFIX_MAP = {
    0: PROPERTIES_PREFIX,
    1: '',
    2: ACTIONS_PREFIX,
}


@attr.s
class DETConfig:
    tables = attr.ib(type=list)

    @property
    def table_names(self):
        return [t.name for t in self.tables]

    def get_table(self, name):
        filtered_tables = [t for t in self.tables if t.name == name]
        assert len(filtered_tables) == 1
        return filtered_tables[0]


@attr.s
class DETTable:
    name = attr.ib()
    source = attr.ib()
    rows = attr.ib(type=list)
    filter_name = attr.ib(default='')
    filter_value = attr.ib(default='')

    @property
    def table_name(self):
        # PG has 64 character limit on table names
        return _truncate(self.name, 3, 63)

    def get_sheet_data(self):
        if len(self.rows) == 0:
            return []
        else:
            for i, row in enumerate(self.rows):
                if i == 0:
                    # the first row also contains the source/filter data
                    yield [
                        row.source_field,
                        row.field,
                        row.map_via,
                        self.source,
                        self.filter_name,
                        self.filter_value,
                    ]
                else:
                    yield [
                        row.source_field,
                        row.field,
                        row.map_via,
                    ]

@attr.s
class DETRow:
    source_field = attr.ib()
    field = attr.ib()
    map_via = attr.ib(default='')


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

    main_table = DETTable(
        name=main_sheet_name,
        source='case',
        filter_name='type',
        filter_value=data['case_type'],
        rows=_get_default_case_rows()
    )
    output = DETConfig(tables=[main_table])

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

            current_table.rows.append(DETRow(source_field=prefixed_path, field=x, map_via=map_via))

    header_sheets = []
    data_sheets = []
    for table in output.tables:
        header_sheets.append((table.name, TITLE_ROW))
        data_sheets.append((table.name, list(table.get_sheet_data())))

    export_raw(header_sheets, data_sheets, output_file, format=Format.XLS_2007)


def _truncate(name, start_char, total_char):
    if len(name) > total_char:
        name = name[:start_char] + '$' + name[-(total_char - (start_char + 1)):]
    return name
