import datetime
import calendar

from dateutil.relativedelta import relativedelta
from dimagi.ext.jsonobject import JsonObject
from jsonobject.base_properties import DefaultProperty
from corehq.apps.userreports.expressions.getters import transform_date, transform_int, \
    transform_datetime
from corehq.apps.userreports.specs import TypeProperty


class AddDaysExpressionSpec(JsonObject):
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


class DiffDaysExpressionSpec(JsonObject):
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


class DiffSecondsExpressionSpec(JsonObject):
    type = TypeProperty('diff_seconds')
    from_expression = DefaultProperty(required=True)
    to_expression = DefaultProperty(required=True)

    def configure(self, from_expression, to_expression):
        self.from_expression = from_expression
        self.to_expression = to_expression

    def __call__(self, item, context=None):
        from_val = transform_datetime(self.from_expression(item, context))
        to_val = transform_datetime(self.to_expression(item, context))
        if from_val is not None and to_val is not None:
            return (to_val - from_val).total_seconds()
        return None
