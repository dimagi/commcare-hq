from dimagi.utils.dates import DateSpan


class FilterValue(object):

    def __init__(self, filter, value):
        self.filter = filter
        self.value = value

    def to_sql_filter(self):
        raise NotImplementedError()

    def to_sql_values(self):
        raise NotImplementedError()

class DateFilterValue(FilterValue):

    def __init__(self, filter, value):
        assert filter.type == 'date'
        # todo: might want some better way to set defaults
        if value is None:
            value = DateSpan.since(7)
        assert isinstance(value, DateSpan)
        super(DateFilterValue, self).__init__(filter, value)

    def to_sql_filter(self):
        return "{} between :startdate and :enddate".format(self.filter.field)

    def to_sql_values(self):
        return {
            'startdate': self.value.startdate,
            'enddate': self.value.enddate,
        }


class ChoiceListFilterValue(FilterValue):

    def __init__(self, filter, value):
        assert filter.type == 'choice_list'
        super(ChoiceListFilterValue, self).__init__(filter, value)

    def to_sql_filter(self):
        return "{} = :value".format(self.filter.field)

    def to_sql_values(self):
        return {
            'value': self.value.value,
        }
