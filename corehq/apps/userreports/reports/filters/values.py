import datetime
from collections import namedtuple

from django.core.urlresolvers import reverse

from sqlagg.filters import (
    BasicFilter,
    BetweenFilter,
    EQFilter,
    GTEFilter,
    GTFilter,
    INFilter,
    ISNULLFilter,
    LTEFilter,
    LTFilter,
    NOTEQFilter,
    NOTNULLFilter,
    get_column,
)
from sqlalchemy import bindparam

from corehq.apps.reports.daterange import get_all_daterange_choices, get_daterange_start_end_dates
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

    def to_es_filter(self):
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

    def to_es_filter(self):
        if self.value is None:
            return None

        return filters.daterange(self.filter.field, lt=self.value.startdate, gt=self.value.enddate)


class NumericFilterValue(FilterValue):
    DBSpecificFilter = namedtuple('DBSpecificFilter', ['sql', 'es'])
    operators_to_filters = {
        '=': DBSpecificFilter(EQFilter, filters.term),
        '!=': DBSpecificFilter(NOTEQFilter, filters.not_term),
        '>=': DBSpecificFilter(GTEFilter, lambda field, val: filters.range_filter(field, gte=val)),
        '>': DBSpecificFilter(GTFilter, lambda field, val: filters.range_filter(field, gt=val)),
        '<=': DBSpecificFilter(LTEFilter, lambda field, val: filters.range_filter(field, lte=val)),
        '<': DBSpecificFilter(LTFilter, lambda field, val: filters.range_filter(field, lt=val)),
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
        filter_class = self.operators_to_filters[self.value['operator']].sql
        return filter_class(self.filter.field, self.filter.slug)

    def to_sql_values(self):
        if self.value is None:
            return {}
        return {
            self.filter.slug: self.value["operand"],
        }

    def to_es_filter(self):
        if self.value is None:
            return None

        filter_class = self.operators_to_filters[self.value['operator']].es
        return filter_class(self.filter.field, self.filter.value)


class BasicBetweenFilter(BasicFilter):
    """
    BasicBetweenFilter implements a BetweenFilter that accepts the
    same constructor arguments as INFilter.

    PreFilterValue uses this to select the filter using
    PreFilterValue.value['operator'] and instantiate either filter the
    same way.
    """
    def build_expression(self, table):
        assert len(self.parameter) == 2
        return get_column(table, self.column_name).between(
            bindparam(self.parameter[0]), bindparam(self.parameter[1])
        )


class PreFilterValue(FilterValue):

    # All dynamic date operators use BasicBetweenFilter
    dyn_date_operators = [c.slug for c in get_all_daterange_choices()]
    null_operator_filters = {
        '=': ISNULLFilter,
        '!=': NOTNULLFilter,
        'is': ISNULLFilter,
        'is not': NOTNULLFilter,
    }
    array_operator_filters = {
        'in': INFilter,
        'between': BasicBetweenFilter,
    }
    scalar_operator_filters = NumericFilterValue.operators_to_filters

    def _is_dyn_date(self):
        return self.value.get('operator') in self.dyn_date_operators

    def _is_null(self):
        return self.value['operand'] is None

    def _is_list(self):
        """
        Returns true if operand should be treated like an array when building
        the query.
        """
        return isinstance(self.value['operand'], list)

    @property
    def _null_filter(self):
        operator = self.value.get('operator') or 'is'
        try:
            return self.null_operator_filters[operator]
        except KeyError:
            raise TypeError('Null value does not support "{}" operator'.format(operator))

    @property
    def _array_filter(self):
        operator = self.value.get('operator') or 'in'
        try:
            return self.array_operator_filters[operator]
        except KeyError:
            raise TypeError('Array value does not support "{}" operator'.format(operator))

    @property
    def _scalar_filter(self):
        operator = self.value.get('operator') or '='
        try:
            return self.scalar_operator_filters[operator]
        except KeyError:
            raise TypeError('Scalar value does not support "{}" operator'.format(operator))

    def to_sql_filter(self):
        if self._is_dyn_date():
            return BasicBetweenFilter(
                self.filter.field,
                get_INFilter_bindparams(self.filter.slug, ['start_date', 'end_date'])
            )
        elif self._is_null():
            return self._null_filter(self.filter.field)
        elif self._is_list():
            return self._array_filter(
                self.filter.field,
                get_INFilter_bindparams(self.filter.slug, self.value['operand'])
            )
        else:
            return self._scalar_filter(self.filter.field, self.filter.slug)

    def to_sql_values(self):
        if self._is_dyn_date():
            start_date, end_date = get_daterange_start_end_dates(self.value['operator'], *self.value['operand'])
            return {
                get_INFilter_element_bindparam(self.filter.slug, i): str(v)
                for i, v in enumerate([start_date, end_date])
            }
        elif self._is_null():
            return {}
        elif self._is_list():
            # Array params work like IN bind params
            return {
                get_INFilter_element_bindparam(self.filter.slug, i): v
                for i, v in enumerate(self.value['operand'])
            }
        else:
            return {self.filter.slug: self.value['operand']}


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
