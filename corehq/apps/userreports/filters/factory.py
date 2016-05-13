import json
import warnings
from django.utils.translation import ugettext as _
from jsonobject.exceptions import BadValueError, WrappingAttributeError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.filters.specs import (PropertyMatchFilterSpec, NotFilterSpec, NamedFilterSpec,
    BooleanExpressionFilterSpec)
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.filters import ANDFilter, ORFilter, NOTFilter, SinglePropertyValueFilter
from corehq.apps.userreports.operators import equal, get_operator


def _build_compound_filter(spec, context):
    compound_type_map = {
        'or': ORFilter,
        'and': ANDFilter,
    }
    if spec['type'] not in compound_type_map:
        raise BadSpecError(_('Complex filter type {0} must be one of the following choices ({1})').format(
            spec['type'],
            ', '.join(compound_type_map.keys())
        ))
    elif not isinstance(spec.get('filters'), list):
        raise BadSpecError(_('{0} filter type must include a "filters" list'.format(spec['type'])))

    filters = [FilterFactory.from_spec(subspec, context) for subspec in spec['filters']]
    return compound_type_map[spec['type']](filters)


def _build_not_filter(spec, context):
    wrapped = NotFilterSpec.wrap(spec)
    return NOTFilter(FilterFactory.from_spec(wrapped.filter, context))


def _build_property_match_filter(spec, context):
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


def _build_boolean_expression_filter(spec, context):
    wrapped = BooleanExpressionFilterSpec.wrap(spec)
    return SinglePropertyValueFilter(
        expression=ExpressionFactory.from_spec(wrapped.expression, context),
        operator=get_operator(wrapped.operator),
        reference_expression=ExpressionFactory.from_spec(wrapped.property_value, context),
    )


def _build_named_filter(spec, context):
    wrapped = NamedFilterSpec.wrap(spec)
    return context.named_filters[wrapped.name]


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
    def from_spec(cls, spec, context=None):
        cls.validate_spec(spec)
        try:
            return cls.constructor_map[spec['type']](spec, context)
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
                    ', '.join(self.constructor_map.keys())
                ))
            )
