from dimagi.utils.dates import DateSpan


SHOW_ALL_CHOICE = '_all'  # todo: if someone wants to name an actually choice "_all" this will break


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
            # default to one week
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

    @property
    def show_all(self):
        return self.value.value == SHOW_ALL_CHOICE

    def to_sql_filter(self):
        if self.show_all:
            return ''
        return '{} = :value'.format(self.filter.field)

    def to_sql_values(self):
        if self.show_all:
            return {}
        return {
            'value': self.value.value,
        }
