from corehq.apps.reports.datatables import (
    DataTablesColumn,
    DataTablesHeader,
    DTSortType,
)


class EsColumnConfig(object):
    """
    Stub object to send column information to the data source
    """

    def __init__(self, columns, headers=None, warnings=None):
        self.columns = columns
        if headers is not None:
            self.headers = [c.header for c in self.columns]
        else:
            self.headers = headers
        self.warnings = warnings if warnings is not None else []


class EsColumn(object):
    def __init__(self, header, format_fn=None, *args, **kwargs):
        self.header = header
        self.format_fn = format_fn
        self.data_tables_column = DataTablesColumn(header, *args, **kwargs)
