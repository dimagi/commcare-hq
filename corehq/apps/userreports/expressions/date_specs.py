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
