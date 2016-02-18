import datetime
import calendar

from dateutil.relativedelta import relativedelta
from dimagi.ext.jsonobject import JsonObject
from jsonobject.base_properties import DefaultProperty
from corehq.apps.userreports.expressions.getters import transform_date, transform_int
from corehq.apps.userreports.specs import TypeProperty


class AddMonthsExpressionSpec(JsonObject):
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


class MonthStartDateExpressionSpec(JsonObject):
    type = TypeProperty('month_start_date')
    date_expression = DefaultProperty(required=True)

    def configure(self, date_expression):
        self._date_expression = date_expression

    def __call__(self, item, context=None):
        date_val = transform_date(self._date_expression(item, context))
        if date_val is not None:
            return datetime.date(date_val.year, date_val.month, 1)
        return None


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
