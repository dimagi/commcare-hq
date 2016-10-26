from corehq.apps.userreports.const import DEFAULT_MAXIMUM_EXPANSION
from corehq.apps.userreports.util import get_indicator_adapter


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


def get_distinct_values(data_source_configuration, column_config, expansion_limit=DEFAULT_MAXIMUM_EXPANSION):
    """
    Return a tuple. The first item is a list of distinct values in the given
    ExpandedColumn no longer than expansion_limit. The second is a boolean which
    is True if the number of distinct values in the column is greater than the
    limit.

    :param data_source_configuration:
    :param column_config:
    :param expansion_limit:
    :return:
    """
    adapter = get_indicator_adapter(data_source_configuration)
    return adapter.get_distinct_values(column_config, expansion_limit)
