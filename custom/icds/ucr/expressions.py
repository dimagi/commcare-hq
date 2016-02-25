from corehq.apps.userreports.specs import TypeProperty
from corehq.apps.userreports.expressions.getters import transform_date
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from dimagi.ext.jsonobject import JsonObject
from jsonobject.base_properties import DefaultProperty

from custom.icds.models import ChildHealthCaseRow


CUSTOM_UCR_EXPRESSIONS = [
    ("icds_indicator_expression", "custom.icds.ucr.expressions.icds_indicator_expression")
]

CASE_TYPE_TO_MODEL_MAPPING = {
    'child_health': ChildHealthCaseRow,
}


class ICDSIndicatorExpressionSpec(JsonObject):
    type = TypeProperty('icds_indicator_expression')
    case_type = DefaultProperty(required=True)
    indicator_name = DefaultProperty(required=True)
    start_date = DefaultProperty(required=True)
    end_date = DefaultProperty(required=True)

    def configure(self, start_date, end_date):
        self._start_date = start_date
        self._end_date = end_date

    def __call__(self, item, context=None):
        start_date = self._start_date(item, context)
        end_date = self._end_date(item, context)

        case_model = CASE_TYPE_TO_MODEL_MAPPING.get(self.case_type, None)
        case_doc = context.root_doc
        child_health_case = case_model(case_doc, transform_date(start_date), transform_date(end_date))

        return getattr(child_health_case, self.indicator_name, None)


def icds_indicator_expression(spec, context):
    wrapped = ICDSIndicatorExpressionSpec.wrap(spec)
    wrapped.configure(
        start_date=ExpressionFactory.from_spec(wrapped.start_date, context),
        end_date=ExpressionFactory.from_spec(wrapped.end_date, context)
    )
    return wrapped
