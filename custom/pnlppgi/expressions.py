from corehq.apps.userreports.specs import TypeProperty
from dimagi.ext.jsonobject import JsonObject, StringProperty
from dimagi.utils.dates import force_to_datetime


class WeekExpressionSpec(JsonObject):
    type = TypeProperty('week_expression')
    property = StringProperty()

    def __call__(self, item, context=None):
        date = force_to_datetime(item[self.property])
        return date.isocalendar()[1]


class YearExpressionSpec(JsonObject):
    type = TypeProperty('year_expression')
    property = StringProperty()

    def __call__(self, item, context=None):
        date = force_to_datetime(item[self.property])
        return date.year


def week_expression(spec, context):
    wrapped = WeekExpressionSpec.wrap(spec)
    return wrapped


def year_expression(spec, context):
    wrapped = YearExpressionSpec.wrap(spec)
    return wrapped
