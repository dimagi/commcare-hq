from corehq.apps.userreports.specs import TypeProperty
from dimagi.ext.jsonobject import JsonObject

from ..models import ChildHealthCaseRow


CUSTOM_UCR_EXPRESSIONS = [
    ("child_health_property", "custom.icds.ucr.expressions.child_health_expression")
]


class ChildHealthIndicatorExpressionSpec(JsonObject):
    type = TypeProperty('child_health_property')
    indicator_name = TypeProperty('indicator_name')

    def __call__(self, item, context=None):
        case_doc = item['case']
        child_health_case = ChildHealthCaseRow(case_doc, context["iteration_month"])
        return getattr(child_health_case, self.indicator_name, None)


def child_health_expression(spec, context):
    wrapped = ChildHealthIndicatorExpressionSpec.wrap(spec)
    return wrapped
