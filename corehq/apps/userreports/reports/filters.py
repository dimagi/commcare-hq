from django.core.urlresolvers import reverse
from sqlagg.filters import BasicFilter, BetweenFilter, EQFilter, ISNULLFilter
from dimagi.utils.dates import DateSpan


SHOW_ALL_CHOICE = '_all'  # todo: if someone wants to name an actually choice "_all" this will break
NONE_CHOICE = u"\u2400"


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
        assert isinstance(value, DateSpan) or value is None
        super(DateFilterValue, self).__init__(filter, value)

    def to_sql_filter(self):
        if self.value is None:
            return ""
        return BetweenFilter(self.filter.field, 'startdate', 'enddate')

    def to_sql_values(self):
        if self.value is None:
            return {}
        return {
            'startdate': self.value.startdate,
            'enddate': self.value.enddate,
        }


class NumericFilterValue(FilterValue):

    def __init__(self, filter, value):
        assert filter.type == "numeric"
        assert (isinstance(value, dict) and "operator" in value and "operand" in value) or value is None
        assert value['operator'] in ["=", "!=", "<", "<=", ">", ">="]
        assert isinstance(value['operand'], int) or isinstance(value['operand'], float)
        super(NumericFilterValue, self).__init__(filter, value)

    def to_sql_filter(self):
        if self.value is None:
            return ""
        ret = BasicFilter(self.filter.field, 'operand',
                          operator=self.value['operator'])
        return ret

    def to_sql_values(self):
        if self.value is None:
            return {}
        return {
            "operand": self.value["operand"]
        }


class ChoiceListFilterValue(FilterValue):

    def __init__(self, filter, value):
        assert filter.type in ('choice_list', 'dynamic_choice_list')
        super(ChoiceListFilterValue, self).__init__(filter, value)

    @property
    def show_all(self):
        return self.value.value == SHOW_ALL_CHOICE

    @property
    def is_null(self):
        return self.value.value == NONE_CHOICE

    def to_sql_filter(self):
        if self.show_all:
            return ''
        if self.is_null:
            return ISNULLFilter(self.filter.field)
        return EQFilter(self.filter.field, self.filter.field)

    def to_sql_values(self):
        if self.show_all or self.is_null:
            return {}
        return {
            self.filter.field: self.value.value,
        }

def dynamic_choice_list_url(domain, report, filter):
    return reverse('choice_list_api', args=[domain, report.spec._id, filter.name])
