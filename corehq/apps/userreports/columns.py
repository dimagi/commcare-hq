class ColumnConfig(object):
    """
    Stub object to send column information to the data source
    """

    def __init__(self, columns, headers=None, warnings=None):
        self.columns = columns
        # default headers to column headers, but allow subclasses to override
        if headers is not None:
            self.headers = [c.header for c in self.columns]
        else:
            self.headers = headers
        self.warnings = warnings if warnings is not None else []
