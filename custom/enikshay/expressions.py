from jsonobject.properties import ListProperty, StringProperty

from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import TypeProperty
from dimagi.ext.jsonobject import JsonObject


class ConcatenateStrings(JsonObject):
    type = TypeProperty('concatenate_strings')
    expressions = ListProperty(required=True)
    separator = StringProperty(required=True)

    def configure(self, expressions):
        self._expression_fns = expressions

    def __call__(self, item, context=None):
        return self.separator.join(
            [
                unicode(expression(item, context)) for expression in self._expression_fns
                if expression(item, context) is not None
            ]
        )


def concatenate_strings_expression(spec, context):
    wrapped = ConcatenateStrings.wrap(spec)
    wrapped.configure(
        [ExpressionFactory.from_spec(e, context) for e in wrapped.expressions],
    )
    return wrapped
