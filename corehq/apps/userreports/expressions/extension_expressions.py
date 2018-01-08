from __future__ import absolute_import
from corehq.apps.userreports.expressions import ExpressionFactory
from corehq.apps.userreports.specs import TypeProperty
from dimagi.ext.jsonobject import JsonObject, StringProperty, DictProperty

CUSTOM_UCR_EXPRESSIONS = [
    ('indexed_case', 'corehq.apps.userreports.expressions.indexed_case_expression'),
]


class IndexedCaseExpressionSpec(JsonObject):
    type = TypeProperty('indexed_case')
    case_expression = DictProperty(required=True)
    index = StringProperty(required=False)

    def configure(self, case_expression, context):
        self._case_expression = case_expression

        index = self.index or 'parent'
        spec = {
            'type': 'related_doc',
            'related_doc_type': 'CommCareCase',
            'doc_id_expression': {
                'type': 'nested',
                'argument_expression': self.case_expression,
                'value_expression': {
                    'type': 'nested',
                    'argument_expression': {
                        'type': 'array_index',
                        'array_expression': {
                            'type': 'filter_items',
                            'items_expression': {
                                'datatype': 'array',
                                'type': 'property_name',
                                'property_name': 'indices'
                            },
                            'filter_expression': {
                                'type': 'boolean_expression',
                                'operator': 'eq',
                                'property_value': index,
                                'expression': {
                                    'type': 'property_name',
                                    'property_name': 'identifier'
                                }
                            }
                        },
                        'index_expression': {
                            'type': 'constant',
                            'constant': 0
                        }
                    },
                    'value_expression': {
                        'type': 'property_name',
                        'property_name': 'referenced_id'
                    }
                }
            },
            'value_expression': {
                'type': 'identity'
            }
        }
        self._expression = ExpressionFactory.from_spec(spec, context)

    def __call__(self, item, context=None):
        return self._expression(item, context)

    def __str__(self):
        return "{case}/{index}".format(
            case=str(self._case_expression),
            index=self.index or "parent"
        )


def indexed_case_expression(spec, context):
    wrapped = IndexedCaseExpressionSpec.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.case_expression, context),
        context
    )
    return wrapped
