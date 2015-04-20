from jsonobject import JsonObject
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import TypeProperty


class AbtSupervisorExpressionSpec(JsonObject):
    # TODO:
    # This class is a stub added to demonstrate UCR expression plugin usage
    # This class will be filled out in a PR coming soon - NC 4/20/15
    type = TypeProperty('abt_supervisor')

    def __call__(self, item, context=None):
        return item

@ExpressionFactory.register("abt_supervisor")
def _abt_supervisor_expression(spec, context):
    wrapped = AbtSupervisorExpressionSpec.wrap(spec)
    return wrapped
