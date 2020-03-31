import attr


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
