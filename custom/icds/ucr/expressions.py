from corehq.apps.userreports.specs import TypeProperty
from corehq.apps.userreports.expressions.getters import transform_date
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from dimagi.ext.jsonobject import JsonObject
from jsonobject.base_properties import DefaultProperty

from custom.icds.models import ChildHealthCaseRow


CUSTOM_UCR_EXPRESSIONS = [
    ("child_health_property", "custom.icds.ucr.expressions.child_health_expression")
]


class ChildHealthIndicatorExpressionSpec(JsonObject):
    type = TypeProperty('child_health_property')
    indicator_name = DefaultProperty(required=True)
    start_date = DefaultProperty(required=True)
    end_date = DefaultProperty(required=True)

    def configure(self, start_date, end_date):
        self._start_date = start_date
        self._end_date = end_date

    def __call__(self, item, context=None):
        case_doc = context.root_doc

        start_date = self._start_date(item, context)
        end_date = self._end_date(item, context)

        child_health_case = ChildHealthCaseRow(case_doc, transform_date(start_date), transform_date(end_date))

        return getattr(child_health_case, self.indicator_name, None)


def child_health_expression(spec, context):
    wrapped = ChildHealthIndicatorExpressionSpec.wrap(spec)
    wrapped.configure(
        start_date=ExpressionFactory.from_spec(wrapped.start_date, context),
        end_date=ExpressionFactory.from_spec(wrapped.end_date, context)
    )
    return wrapped
