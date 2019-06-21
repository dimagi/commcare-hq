from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
import calendar

from dateutil.relativedelta import relativedelta
from dimagi.ext.jsonobject import JsonObject
from jsonobject.base_properties import DefaultProperty
from corehq.apps.userreports.expressions.getters import transform_date, transform_int
from corehq.apps.userreports.specs import TypeProperty


class AddDaysExpressionSpec(JsonObject):
    """
    Below is a simple example that demonstrates the structure. The
    expression below will add 28 days to a property called "dob". The
    date_expression and count_expression can be any valid expressions, or
    simply constants.

    .. code:: json

       {
           "type": "add_days",
           "date_expression": {
               "type": "property_name",
               "property_name": "dob",
           },
           "count_expression": 28
       }
    """
    type = TypeProperty('add_days')
    date_expression = DefaultProperty(required=True)
    count_expression = DefaultProperty(required=True)

    def configure(self, date_expression, count_expression):
        self._date_expression = date_expression
        self._count_expression = count_expression

    def __call__(self, item, context=None):
        date_val = transform_date(self._date_expression(item, context))
        int_val = transform_int(self._count_expression(item, context))
        if date_val is not None and int_val is not None:
            return date_val + datetime.timedelta(days=int_val)
        return None

    def __str__(self):
        return "add_day({date}, {count})".format(
            date=self._date_expression,
            count=self._count_expression)


class AddMonthsExpressionSpec(JsonObject):
    """
    ``add_months`` offsets given date by given number of calendar months. If
    offset results in an invalid day (for e.g. Feb 30, April 31), the day of
    resulting date will be adjusted to last day of the resulting calendar
    month.

    The date_expression and months_expression can be any valid expressions,
    or simply constants, including negative numbers.

    .. code:: json

       {
           "type": "add_months",
           "date_expression": {
               "type": "property_name",
               "property_name": "dob",
           },
           "months_expression": 28
       }
    """
    type = TypeProperty('add_months')
    date_expression = DefaultProperty(required=True)
    months_expression = DefaultProperty(required=True)

    def configure(self, date_expression, months_expression):
        self._date_expression = date_expression
        self._months_expression = months_expression

    def __call__(self, item, context=None):
        date_val = transform_date(self._date_expression(item, context))
        months_count_val = transform_int(self._months_expression(item, context))
        if date_val is not None and months_count_val is not None:
            return date_val + relativedelta(months=months_count_val)
        return None

    def __str__(self):
        return "add_month({date}, {month})".format(
            date=self._date_expression,
            month=self._months_expression)


class MonthStartDateExpressionSpec(JsonObject):
    """
    ``month_start_date`` returns date of first day in the month of given
    date and ``month_end_date`` returns date of last day in the month of
    given date.

    The ``date_expression`` can be any valid expression, or simply constant

    .. code:: json

       {
           "type": "month_start_date",
           "date_expression": {
               "type": "property_name",
               "property_name": "dob",
           },
       }
    """
    type = TypeProperty('month_start_date')
    date_expression = DefaultProperty(required=True)

    def configure(self, date_expression):
        self._date_expression = date_expression

    def __call__(self, item, context=None):
        date_val = transform_date(self._date_expression(item, context))
        if date_val is not None:
            return datetime.date(date_val.year, date_val.month, 1)
        return None

    def __str__(self):
        return "first_day({})".format(self._date_expression)


class MonthEndDateExpressionSpec(JsonObject):
    type = TypeProperty('month_end_date')
    date_expression = DefaultProperty(required=True)

    def configure(self, date_expression):
        self._date_expression = date_expression

    def __call__(self, item, context=None):
        date_val = transform_date(self._date_expression(item, context))
        if date_val is not None:
            first_week_day, last_day = calendar.monthrange(date_val.year, date_val.month)
            return datetime.date(date_val.year, date_val.month, last_day)
        return None

    def __str__(self):
        return "last_day({})".format(self._date_expression)


class DiffDaysExpressionSpec(JsonObject):
    """
    ``diff_days`` returns number of days between dates specified by
    ``from_date_expression`` and ``to_date_expression``. The
    from_date_expression and to_date_expression can be any valid
    expressions, or simply constants.

    .. code:: json

       {
           "type": "diff_days",
           "from_date_expression": {
               "type": "property_name",
               "property_name": "dob",
           },
           "to_date_expression": "2016-02-01"
       }
    """
    type = TypeProperty('diff_days')
    from_date_expression = DefaultProperty(required=True)
    to_date_expression = DefaultProperty(required=True)

    def configure(self, from_date_expression, to_date_expression):
        self._from_date_expression = from_date_expression
        self._to_date_expression = to_date_expression

    def __call__(self, item, context=None):
        from_date_val = transform_date(self._from_date_expression(item, context))
        to_date_val = transform_date(self._to_date_expression(item, context))
        if from_date_val is not None and to_date_val is not None:
            return (to_date_val - from_date_val).days
        return None

    def __str__(self):

        return "({}) - ({})".format(self._to_date_expression, self._from_date_expression)
