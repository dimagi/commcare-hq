import attr

from couchexport.export import export_raw
from couchexport.models import Format

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


@attr.s
class DETConfig:
    name = attr.ib()
    tables = attr.ib(factory=list)

    @property
    def table_names(self):
        return [t.name for t in self.tables]

    def get_table(self, name):
        filtered_tables = [t for t in self.tables if t.name == name]
        assert len(filtered_tables) == 1
        return filtered_tables[0]

    def export_to_file(self, output_file):
        header_sheets = []
        data_sheets = []
        for table in self.tables:
            header_sheets.append((table.name, TITLE_ROW))
            data_sheets.append((table.name, list(table.get_sheet_data())))

        export_raw(header_sheets, data_sheets, output_file, format=Format.XLS_2007)


@attr.s
class DETTable:
    name = attr.ib()
    source = attr.ib()
    rows = attr.ib(factory=list)
    filter_name = attr.ib(default='')
    filter_value = attr.ib(default='')

    def get_sheet_data(self):
        if not self.rows:
            return
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
