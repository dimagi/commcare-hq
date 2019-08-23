import datetime
import sqlalchemy

from django.urls import reverse
from memoized import memoized
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
    ANDFilter,
    ORFilter)

from corehq.apps.reports.daterange import get_all_daterange_choices, get_daterange_start_end_dates
from corehq.apps.reports.util import (
    get_INFilter_bindparams,
    get_INFilter_element_bindparam,
)

from dimagi.utils.dates import DateSpan


SHOW_ALL_CHOICE = '_all'  # todo: if someone wants to name an actually choice "_all" this will break
NONE_CHOICE = "\u2400"
CHOICE_DELIMITER = "\u001f"


class FilterValue(object):

    def __init__(self, filter, value):
        """
        args:
            filter: should be a raw filter spec, the filter dict
                defined in the ReportConfiguraion
            value: should be the filter value from the user request
        """
        self.filter = filter
        self.value = value

    def to_sql_filter(self):
        raise NotImplementedError()

    def to_sql_values(self):
        raise NotImplementedError()


class DateFilterValue(FilterValue):

    def __init__(self, filter, value):
        assert filter['type'] == 'date'
        assert isinstance(value, DateSpan) or value is None
        super(DateFilterValue, self).__init__(filter, value)

    def to_sql_filter(self):
        if self.value is None:
            return None
        if self.value.startdate is None:
            return LTFilter(
                self.filter['field'],
                '%s_enddate' % self.filter['slug'])
        elif self.value.enddate is None:
            return GTFilter(
                self.filter['field'],
                '%s_startdate' % self.filter['slug']
            )
        else:
            return BetweenFilter(
                self.filter['field'],
                '%s_startdate' % self.filter['slug'],
                '%s_enddate' % self.filter['slug']
            )

    def to_sql_values(self):
        if self.value is None:
            return {}

        startdate = self.value.startdate
        enddate = self.value.enddate

        if self.value.inclusive:
            enddate = self._offset_enddate(enddate)

        if self.filter.get('compare_as_string'):
            startdate = str(startdate) if startdate is not None else None
            enddate = str(enddate) if enddate is not None else None

        sql_values = {}
        if startdate is not None:
            sql_values.update({'%s_startdate' % self.filter['slug']: startdate})
        if enddate is not None:
            sql_values.update({'%s_enddate' % self.filter['slug']: enddate})

        return sql_values

    def _offset_enddate(self, enddate):
        # offset enddate for SQL query
        if enddate:
            enddate = datetime.datetime.combine(enddate, datetime.datetime.max.time())
        return enddate


class QuarterFilterValue(FilterValue):

    @property
    def startdate_slug(self):
        return '%s_startdate' % self.filter['slug']

    @property
    def enddate_slug(self):
        return '%s_enddate' % self.filter['slug']

    def to_sql_filter(self):
        return ANDFilter([
            GTEFilter(self.filter['field'], self.startdate_slug),
            LTFilter(self.filter['field'], self.enddate_slug)
        ])

    def to_sql_values(self):
        return {
            self.startdate_slug: self.value.computed_startdate,
            self.enddate_slug: self.value.computed_enddate
        }


class IsDistinctFromFilter(BasicFilter):

    def build_expression(self):
        return sqlalchemy.column(self.column_name).is_distinct_from(sqlalchemy.bindparam(self.parameter))


class NumericFilterValue(FilterValue):
    operators_to_filters = {
        '=': EQFilter,
        '!=': NOTEQFilter,
        'distinct from': IsDistinctFromFilter,
        '>=': GTEFilter,
        '>': GTFilter,
        '<=': LTEFilter,
        '<': LTFilter,
    }

    def __init__(self, filter, value):
        assert filter['type'] == "numeric"
        assert (isinstance(value, dict) and "operator" in value and "operand" in value) or value is None
        if value:
            assert value['operator'] in self.operators_to_filters
            assert isinstance(value['operand'], int) or isinstance(value['operand'], float)
        super(NumericFilterValue, self).__init__(filter, value)

    def to_sql_filter(self):
        if self.value is None:
            return None
        filter_class = self.operators_to_filters[self.value['operator']]
        return filter_class(self.filter['field'], self.filter['slug'])

    def to_sql_values(self):
        if self.value is None:
            return {}
        return {
            self.filter['slug']: self.value["operand"],
        }


class BasicBetweenFilter(BasicFilter):
    """
    BasicBetweenFilter implements a BetweenFilter that accepts the
    same constructor arguments as INFilter.

    PreFilterValue uses this to select the filter using
    PreFilterValue.value['operator'] and instantiate either filter the
    same way.
    """
    def build_expression(self):
        assert len(self.parameter) == 2
        return sqlalchemy.column(self.column_name).between(
            sqlalchemy.bindparam(self.parameter[0]), sqlalchemy.bindparam(self.parameter[1])
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
                self.filter['field'],
                get_INFilter_bindparams(self.filter['slug'], ['start_date', 'end_date'])
            )
        elif self._is_null():
            return self._null_filter(self.filter['field'])
        elif self._is_list():
            return self._array_filter(
                self.filter['field'],
                get_INFilter_bindparams(self.filter['slug'], self.value['operand'])
            )
        else:
            return self._scalar_filter(self.filter['field'], self.filter['slug'])

    def to_sql_values(self):
        if self._is_dyn_date():
            start_date, end_date = get_daterange_start_end_dates(self.value['operator'], *self.value['operand'])
            return {
                get_INFilter_element_bindparam(self.filter['slug'], i): str(v)
                for i, v in enumerate([start_date, end_date])
            }
        elif self._is_null():
            return {}
        elif self._is_list():
            # Array params work like IN bind params
            return {
                get_INFilter_element_bindparam(self.filter['slug'], i): v
                for i, v in enumerate(self.value['operand'])
            }
        else:
            return {self.filter['slug']: self.value['operand']}


class ChoiceListFilterValue(FilterValue):

    ALLOWED_TYPES = ('choice_list', 'dynamic_choice_list', 'multi_field_dynamic_choice_list')

    def __init__(self, filter, value):
        assert filter['type'] in self.ALLOWED_TYPES
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

    @property
    def _ancestor_filter(self):
        """
        Returns an instance of AncestorSQLParams per the spec, returns None
            if it is not applicable
        """
        ancestor_expression = self.filter.get('ancestor_expression')
        if not (self.show_all and self.show_none) and ancestor_expression:
            if len(self.value) > 1:
                # if multiple locations are passed, for partition to work
                #   multiple ancestor locations should be passed, but that
                #   would require multiple DB calls. So instead don't pass
                #   any ancestors at all
                return None
            location = self.value[0].value
            params = AncestorSQLParams(self.filter['ancestor_expression'], location)
            if params.sql_value():
                return params

    def to_sql_filter(self):
        if self.show_all:
            return None
        if self.is_null:
            return ISNULLFilter(self.filter['field'])

        in_filter = INFilter(
            self.filter['field'],
            get_INFilter_bindparams(self.filter['slug'], self.value)
        )
        if self._ancestor_filter:
            return ANDFilter(
                [self._ancestor_filter.sql_filter(), in_filter]
            )
        else:
            return in_filter

    def to_sql_values(self):
        if self.show_all or self.is_null:
            return {}
        values = {
            get_INFilter_element_bindparam(self.filter['slug'], i): val.value
            for i, val in enumerate(self.value)
        }
        if self._ancestor_filter:
            values.update(self._ancestor_filter.sql_value())
        return values


class MultiFieldChoiceListFilterValue(ChoiceListFilterValue):
    ALLOWED_TYPES = ('multi_field_dynamic_choice_list', )

    def to_sql_filter(self):
        if self.show_all:
            return None
        if self.is_null:
            return ORFilter([ISNULLFilter(field) for field in self.filter.get('fields')])
        return ORFilter([
            INFilter(
                field,
                get_INFilter_bindparams(self.filter['slug'], self.value)
            ) for field in self.filter.get('fields')
        ])


class LocationDrilldownFilterValue(FilterValue):
    SHOW_NONE = "show_none"
    SHOW_ALL = "show_all"

    @property
    def show_all(self):
        return self.value == self.SHOW_ALL

    @property
    def show_none(self):
        return self.value == self.SHOW_NONE

    @property
    def _ancestor_filter(self):
        ancestor_expression = self.filter.get('ancestor_expression')
        if (not (self.show_all and self.show_none) and
           ancestor_expression and len(self.value) == 1):
            params = AncestorSQLParams(self.filter['ancestor_expression'], self.value[0])
            if params.sql_value():
                return params

    def to_sql_filter(self):
        if self.show_all:
            return None

        in_filter = INFilter(
            self.filter['field'],
            get_INFilter_bindparams(self.filter['slug'], [None] if self.show_none else self.value)
        )

        if self._ancestor_filter:
            return ANDFilter(
                [self._ancestor_filter.sql_filter(), in_filter]
            )
        else:
            return in_filter

    def to_sql_values(self):
        if self.show_all:
            return {}
        values = {
            get_INFilter_element_bindparam(self.filter['slug'], i): val
            for i, val in enumerate([None] if self.show_none else self.value)
        }
        if self._ancestor_filter:
            values.update(self._ancestor_filter.sql_value())
        return values


class AncestorSQLParams(object):
    def __init__(self, ancestor_expression, location_id):
        self.ancestor_expression = ancestor_expression
        self.location_id = location_id

    def sql_filter(self):
        return EQFilter(self.ancestor_expression['field'], self.ancestor_expression['field'])

    @memoized
    def sql_value(self):
        # all locations in self.value will have same ancestor, so just pick first one to query
        from corehq.apps.locations.models import SQLLocation
        location = SQLLocation.by_location_id(self.location_id)
        if location:
            ancestor = location.get_ancestor_of_type(
                self.ancestor_expression['location_type']
            )
        else:
            return None
        if ancestor:
            return {
                self.ancestor_expression['field']: ancestor.location_id
            }
        else:
            return None


def dynamic_choice_list_url(domain, report, filter):
    # filter must be an instance of DynamicChoiceListFilter
    return reverse('choice_list_api', args=[domain, report.spec._id, filter.name])
