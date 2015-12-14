import functools
import json
from django.utils.translation import ugettext as _
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.specs import PropertyNameGetterSpec, PropertyPathGetterSpec, \
    ConditionalExpressionSpec, ConstantGetterSpec, RootDocExpressionSpec, RelatedDocExpressionSpec, \
    IdentityExpressionSpec, IteratorExpressionSpec, SwitchExpressionSpec, ArrayIndexExpressionSpec, \
    NestedExpressionSpec, DictExpressionSpec, NamedExpressionSpec
from dimagi.utils.web import json_handler


def _make_filter(spec, context):
    # just pulled out here to keep the inline imports to a minimum
    # no way around this since the two factories inherently depend on each other
    from corehq.apps.userreports.filters.factory import FilterFactory
    return FilterFactory.from_spec(spec, context)


def _simple_expression_generator(wrapper_class, spec, context):
    return wrapper_class.wrap(spec)


_identity_expression = functools.partial(_simple_expression_generator, IdentityExpressionSpec)
_constant_expression = functools.partial(_simple_expression_generator, ConstantGetterSpec)
_property_name_expression = functools.partial(_simple_expression_generator, PropertyNameGetterSpec)
_property_path_expression = functools.partial(_simple_expression_generator, PropertyPathGetterSpec)


def _named_expression(spec, context):
    expression = NamedExpressionSpec.wrap(spec)
    expression.configure(context=context)
    return expression


def _conditional_expression(spec, context):
    wrapped = ConditionalExpressionSpec.wrap(spec)
    wrapped.configure(
        _make_filter(wrapped.test, context),
        ExpressionFactory.from_spec(wrapped.expression_if_true, context),
        ExpressionFactory.from_spec(wrapped.expression_if_false, context),
    )
    return wrapped


def _switch_expression(spec, context):
    wrapped = SwitchExpressionSpec.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.switch_on, context),
        {k: ExpressionFactory.from_spec(v, context) for k, v in wrapped.cases.iteritems()},
        ExpressionFactory.from_spec(wrapped.default, context),
    )
    return wrapped


def _array_index_expression(spec, context):
    wrapped = ArrayIndexExpressionSpec.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.array_expression, context),
        ExpressionFactory.from_spec(wrapped.index_expression, context),
    )
    return wrapped


def _root_doc_expression(spec, context):
    wrapped = RootDocExpressionSpec.wrap(spec)
    wrapped.configure(ExpressionFactory.from_spec(wrapped.expression, context))
    return wrapped


def _related_doc_expression(spec, context):
    wrapped = RelatedDocExpressionSpec.wrap(spec)
    wrapped.configure(
        doc_id_expression=ExpressionFactory.from_spec(wrapped.doc_id_expression, context),
        value_expression=ExpressionFactory.from_spec(wrapped.value_expression, context),
    )
    return wrapped


def _iterator_expression(spec, context):
    wrapped = IteratorExpressionSpec.wrap(spec)
    wrapped.configure(
        expressions=[ExpressionFactory.from_spec(e) for e in wrapped.expressions],
        test=_make_filter(wrapped.test, context) if wrapped.test else None
    )
    return wrapped


def _nested_expression(spec, context):
    wrapped = NestedExpressionSpec.wrap(spec)
    wrapped.configure(
        argument_expression=ExpressionFactory.from_spec(wrapped.argument_expression),
        value_expression=ExpressionFactory.from_spec(wrapped.value_expression),
    )
    return wrapped


def _dict_expression(spec, context):
    wrapped = DictExpressionSpec.wrap(spec)
    compiled_properties = {key: ExpressionFactory.from_spec(value) for key, value in wrapped.properties.items()}
    wrapped.configure(
        compiled_properties=compiled_properties,
    )
    return wrapped


class ExpressionFactory(object):
    spec_map = {
        'identity': _identity_expression,
        'constant': _constant_expression,
        'property_name': _property_name_expression,
        'property_path': _property_path_expression,
        'named': _named_expression,
        'conditional': _conditional_expression,
        'array_index': _array_index_expression,
        'root_doc': _root_doc_expression,
        'related_doc': _related_doc_expression,
        'iterator': _iterator_expression,
        'switch': _switch_expression,
        'nested': _nested_expression,
        'dict': _dict_expression,
    }
    # Additional items are added to the spec_map by use of the `register` method.

    @classmethod
    def register(cls, type_name, factory_func):
        """
        Registers an expression factory function for the given type_name.
        Use this method to add additional expression types to UCR.
        """
        if type_name in cls.spec_map:
            raise ValueError(
                "Expression factory function already "
                "registered for type '{}'!".format(type_name)
            )

        cls.spec_map[type_name] = factory_func

    @classmethod
    def from_spec(cls, spec, context=None):
        if _is_constant(spec):
            return cls.from_spec(_convert_constant_to_expression_spec(spec), context)
        try:
            return cls.spec_map[spec['type']](spec, context)
        except KeyError:
            raise BadSpecError(_('Invalid or missing getter type: {}. Valid options are: {}').format(
                spec.get('type', '[missing]'),
                ', '.join(cls.spec_map.keys()),
            ))
        except (TypeError, BadValueError) as e:
            raise BadSpecError(_('Problem creating getter: {}. Message is: {}').format(
                json.dumps(spec, indent=2, default=json_handler),
                str(e),
            ))


def _is_constant(value):
    return isinstance(value, (basestring, int, bool, float))


def _convert_constant_to_expression_spec(value):
    return {'type': 'constant', 'constant': value}
