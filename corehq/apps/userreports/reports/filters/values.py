import datetime

from django.core.urlresolvers import reverse

from sqlagg.filters import (
    BetweenFilter,
    EQFilter,
    GTEFilter,
    GTFilter,
    INFilter,
    ISNULLFilter,
    LTEFilter,
    LTFilter,
    NOTEQFilter,
    RawFilter)
from corehq.apps.reports.util import (
    get_INFilter_bindparams,
    get_INFilter_element_bindparam,
)

from dimagi.utils.dates import DateSpan


SHOW_ALL_CHOICE = '_all'  # todo: if someone wants to name an actually choice "_all" this will break
NONE_CHOICE = u"\u2400"
CHOICE_DELIMITER = u"\u001f"


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
            return None
        if self.value.startdate is None:
            return LTFilter(
                self.filter.field,
                '%s_enddate' % self.filter.slug)
        elif self.value.enddate is None:
            return GTFilter(
                self.filter.field,
                '%s_startdate' % self.filter.slug
            )
        else:
            return BetweenFilter(
                self.filter.field,
                '%s_startdate' % self.filter.slug,
                '%s_enddate' % self.filter.slug
            )

    def to_sql_values(self):
        if self.value is None:
            return {}

        startdate = self.value.startdate
        enddate = self.value.enddate

        if self.value.inclusive:
            enddate = self._offset_enddate(enddate)

        if self.filter.compare_as_string:
            startdate = str(startdate) if startdate is not None else None
            enddate = str(enddate) if enddate is not None else None

        sql_values = {}
        if startdate is not None:
            sql_values.update({'%s_startdate' % self.filter.slug: startdate})
        if enddate is not None:
            sql_values.update({'%s_enddate' % self.filter.slug: enddate})

        return sql_values

    def _offset_enddate(self, enddate):
        # offset enddate for SQL query
        # if it is datetime.date object it should not be offset
        # if it is datetime.datetime object it should be offset to last microsecond of the day
        if enddate and type(enddate) is datetime.datetime:
            enddate = enddate + datetime.timedelta(days=1) - datetime.timedelta.resolution
        return enddate


class NumericFilterValue(FilterValue):
    operators_to_filters = {
        '=': EQFilter,
        '!=': NOTEQFilter,
        '>=': GTEFilter,
        '>': GTFilter,
        '<=': LTEFilter,
        '<': LTFilter,
    }

    def __init__(self, filter, value):
        assert filter.type == "numeric"
        assert (isinstance(value, dict) and "operator" in value and "operand" in value) or value is None
        if value:
            assert value['operator'] in self.operators_to_filters
            assert isinstance(value['operand'], int) or isinstance(value['operand'], float)
        super(NumericFilterValue, self).__init__(filter, value)

    def to_sql_filter(self):
        if self.value is None:
            return None
        filter_class = self.operators_to_filters[self.value['operator']]
        return filter_class(self.filter.field, self.filter.slug)

    def to_sql_values(self):
        if self.value is None:
            return {}
        return {
            self.filter.slug: self.value["operand"],
        }


class PreFilterValue(FilterValue):

    def is_null(self):
        return self.value is None

    def is_list(self):
        return isinstance(self.value, list)

    def to_sql_filter(self):
        if self.is_null():
            return ISNULLFilter(self.filter.field)
        elif self.is_list():
            return INFilter(
                self.filter.field,
                get_INFilter_bindparams(self.filter.slug, self.value)
            )
        else:
            return EQFilter(self.filter.field, self.filter.slug)

    def to_sql_values(self):
        if self.is_null():
            return {}
        elif self.is_list():
            return {
                get_INFilter_element_bindparam(self.filter.slug, i): v
                for i, v in enumerate(self.value)
            }
        else:
            return {self.filter.slug: self.value}


class ChoiceListFilterValue(FilterValue):

    def __init__(self, filter, value):
        assert filter.type in ('choice_list', 'dynamic_choice_list')
        if not isinstance(value, list):
            # if in single selection mode just force it to a list
            value = [value]
        super(ChoiceListFilterValue, self).__init__(filter, value)

    @property
    def show_all(self):
        return SHOW_ALL_CHOICE in [choice.value for choice in self.value]

    @property
    def is_null(self):
        return NONE_CHOICE in [choice.value for choice in self.value]

    def to_sql_filter(self):
        if self.show_all:
            return None
        if self.is_null:
            return ISNULLFilter(self.filter.field)
        return INFilter(
            self.filter.field,
            get_INFilter_bindparams(self.filter.slug, self.value)
        )

    def to_sql_values(self):
        if self.show_all or self.is_null:
            return {}
        return {
            get_INFilter_element_bindparam(self.filter.slug, i): val.value
            for i, val in enumerate(self.value)
        }


def dynamic_choice_list_url(domain, report, filter):
    return reverse('choice_list_api', args=[domain, report.spec._id, filter.name])
