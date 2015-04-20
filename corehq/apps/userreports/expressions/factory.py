import functools
import json
from django.utils.translation import ugettext as _
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.specs import PropertyNameGetterSpec, PropertyPathGetterSpec, \
    ConditionalExpressionSpec, ConstantGetterSpec, RootDocExpressionSpec, RelatedDocExpressionSpec


class ExpressionFactory(object):
    spec_map = {
        'constant': _constant_expression,
        'property_name': _property_name_expression,
        'property_path': _property_path_expression,
        'conditional': _conditional_expression,
        'root_doc': _root_doc_expression,
        'related_doc': _related_doc_expression,
    }

    @classmethod
    def from_spec(cls, spec, context=None):
        try:
            return cls.spec_map[spec['type']](spec, context)
        except KeyError:
            raise BadSpecError(_('Invalid or missing getter type: {}. Valid options are: {}').format(
                spec.get('type', '[missing]'),
                ', '.join(cls.spec_map.keys()),
            ))
        except BadValueError as e:
            raise BadSpecError(_('Problem creating getter: {}. Message is: {}').format(
                json.dumps(spec, indent=2),
                str(e),
            ))


def _simple_expression_generator(wrapper_class, spec, context):
    return wrapper_class.wrap(spec)

_constant_expression = functools.partial(_simple_expression_generator, ConstantGetterSpec)
_property_name_expression = functools.partial(_simple_expression_generator, PropertyNameGetterSpec)
_property_path_expression = functools.partial(_simple_expression_generator, PropertyPathGetterSpec)

def _conditional_expression(spec, context):
    # no way around this since the two factories inherently depend on each other
    from corehq.apps.userreports.filters.factory import FilterFactory
    wrapped = ConditionalExpressionSpec.wrap(spec)
    wrapped.configure(
        FilterFactory.from_spec(wrapped.test, context),
        ExpressionFactory.from_spec(wrapped.expression_if_true, context),
        ExpressionFactory.from_spec(wrapped.expression_if_false, context),
    )
    return wrapped


def _root_doc_expression(spec, context):
    wrapped = RootDocExpressionSpec.wrap(spec)
    wrapped.configure(ExpressionFactory.from_spec(wrapped.expression, context))
    return wrapped


def _related_doc_expression(spec, context):
    wrapped = RelatedDocExpressionSpec.wrap(spec)
    wrapped.configure(
        related_doc_type=wrapped.related_doc_type,
        doc_id_expression=ExpressionFactory.from_spec(wrapped.doc_id_expression, context),
        value_expression=ExpressionFactory.from_spec(wrapped.value_expression, context),
    )
    return wrapped
