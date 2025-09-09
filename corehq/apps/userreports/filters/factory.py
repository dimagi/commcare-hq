import json
import warnings

from django.utils.translation import gettext as _

from jsonobject.exceptions import BadValueError, WrappingAttributeError

from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.filters import (
    ANDFilter,
    NamedFilter,
    NOTFilter,
    ORFilter,
    SinglePropertyValueFilter,
)
from corehq.apps.userreports.filters.specs import (
    BooleanExpressionFilterSpec,
    NamedFilterSpec,
    NotFilterSpec,
    PropertyMatchFilterSpec,
)
from corehq.apps.userreports.operators import equal, get_operator
from corehq.apps.userreports.specs import FactoryContext


def _build_compound_filter(spec, factory_context):
    compound_type_map = {
        'or': ORFilter,
        'and': ANDFilter,
    }
    if spec['type'] not in compound_type_map:
        raise BadSpecError(_('Complex filter type {0} must be one of the following choices ({1})').format(
            spec['type'],
            ', '.join(compound_type_map)
        ))
    elif not isinstance(spec.get('filters'), list):
        raise BadSpecError(_('{0} filter type must include a "filters" list'.format(spec['type'])))

    filters = [FilterFactory.from_spec(subspec, factory_context) for subspec in spec['filters']]
    return compound_type_map[spec['type']](filters)


def _build_not_filter(spec, factory_context):
    wrapped = NotFilterSpec.wrap(spec)
    return NOTFilter(FilterFactory.from_spec(wrapped.filter, factory_context))


def _build_property_match_filter(spec, factory_context):
    warnings.warn(
        "property_match are deprecated. Use boolean_expression instead.",
        DeprecationWarning,
    )
    wrapped = PropertyMatchFilterSpec.wrap(spec)
    return SinglePropertyValueFilter(
        expression=wrapped.getter,
        operator=equal,
        reference_expression=ExpressionFactory.from_spec(wrapped.property_value),
    )


def _build_boolean_expression_filter(spec, factory_context):
    wrapped = BooleanExpressionFilterSpec.wrap(spec)
    return SinglePropertyValueFilter(
        expression=ExpressionFactory.from_spec(wrapped.expression, factory_context),
        operator=get_operator(wrapped.operator),
        reference_expression=ExpressionFactory.from_spec(wrapped.property_value, factory_context),
    )


def _build_named_filter(spec, factory_context):
    wrapped = NamedFilterSpec.wrap(spec)
    filter = factory_context.get_named_filter(wrapped.name)
    return NamedFilter(wrapped.name, filter)


class FilterFactory(object):
    constructor_map = {
        'property_match': _build_property_match_filter,
        'boolean_expression': _build_boolean_expression_filter,
        'and': _build_compound_filter,
        'or': _build_compound_filter,
        'not': _build_not_filter,
        'named': _build_named_filter,
    }

    @classmethod
    def from_spec(cls, spec, factory_context=None):
        factory_context = factory_context or FactoryContext.empty()
        cls.validate_spec(spec)
        try:
            return cls.constructor_map[spec['type']](spec, factory_context)
        except (AssertionError, BadValueError, WrappingAttributeError) as e:
            raise BadSpecError(_('Problem creating filter from spec: {}, message is {}').format(
                json.dumps(spec, indent=2),
                str(e),
            ))

    @classmethod
    def validate_spec(self, spec):
        if spec.get('type') not in self.constructor_map:
            raise BadSpecError(
                _('Illegal or missing filter type: "{0}", must be one of the following choice: ({1})'.format(
                    spec.get('type'),
                    ', '.join(self.constructor_map)
                ))
            )
