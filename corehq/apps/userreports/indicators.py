from fluff import TYPE_INTEGER


class Column(object):
    def __init__(self, id, datatype, is_nullable=True, is_primary_key=False):
        self.id = id
        self.datatype = datatype
        self.is_nullable = is_nullable
        self.is_primary_key = is_primary_key

    def __repr__(self):
        return self.id

class ColumnValue(object):

    def __init__(self, column, value):
        self.column = column
        self.value = value

    def __repr__(self):
        return '{0}: {1}'.format(self.column, self.value)


class ConfigurableIndicatorMixIn(object):

    def get_columns(self):
        raise NotImplementedError()

    def get_values(self, item):
        raise NotImplementedError()

class ConfigurableIndicator(ConfigurableIndicatorMixIn):

    def __init__(self, display_name):
        self.display_name = display_name



class SingleColumnIndicator(ConfigurableIndicator):

    def __init__(self, display_name, column):
        super(SingleColumnIndicator, self).__init__(display_name)
        self.column = column

    def get_columns(self):
        return [self.column]


class BooleanIndicator(SingleColumnIndicator):
    """
    A boolean indicator leverages the filter logic and returns "1" if
    the filter is true, or "0" if it is false.
    """

    def __init__(self, display_name, column_id, filter):
        super(BooleanIndicator, self).__init__(display_name, Column(column_id, datatype=TYPE_INTEGER))
        self.filter = filter

    def get_values(self, item):
        value = 1 if self.filter.filter(item) else 0
        return [ColumnValue(self.column, value)]


class RawIndicator(SingleColumnIndicator):
    """
    Pass whatever's in the column through to the database
    """
    def __init__(self, display_name, column, getter):
        super(RawIndicator, self).__init__(display_name, column)
        self.getter = getter

    def get_values(self, item):
        return [ColumnValue(self.column, self.getter(item))]


class CompoundIndicator(ConfigurableIndicator):
    """
    An indicator that wraps other indicators.
    """
    def __init__(self, display_name, indicators):
        super(CompoundIndicator, self).__init__(display_name)
        self.indicators = indicators

    def get_columns(self):
        return [c for ind in self.indicators for c in ind.get_columns()]

    def get_values(self, item):
        return [val for ind in self.indicators for val in ind.get_values(item)]
