from django.utils.translation import ugettext as _
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.filters import SinglePropertyValueFilter
from corehq.apps.userreports.getters import SimpleGetter
from corehq.apps.userreports.indicators import BooleanIndicator
from corehq.apps.userreports.logic import EQUAL
from fluff.filters import ANDFilter, ORFilter


def _build_compound_filter(spec):
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

    filters = [FilterFactory.from_spec(subspec) for subspec in spec['filters']]
    return compound_type_map[spec['type']](filters)


def _build_property_match_filter(spec):
    _validate_required_fields(spec, ('property_name', 'property_value'))

    return SinglePropertyValueFilter(
        getter=SimpleGetter(spec['property_name']),
        operator=EQUAL,
        reference_value=spec['property_value']
    )


class FilterFactory(object):
    constructor_map = {
        'property_match': _build_property_match_filter,
        'and': _build_compound_filter,
        'or': _build_compound_filter,
    }

    @classmethod
    def from_spec(cls, spec):
        cls.validate_spec(spec)
        return cls.constructor_map[spec['type']](spec)

    @classmethod
    def validate_spec(self, spec):
        _validate_required_fields(spec, ('type',))
        if spec['type'] not in self.constructor_map:
            raise BadSpecError(_('Illegal filter type: "{0}", must be one of the following choice: ({1})'.format(
                spec['type'],
                ', '.join(self.constructor_map.keys())
            )))


def _build_boolean_indicator(spec):
    _validate_required_fields(spec, ('column_id', 'filter'))
    if not isinstance(spec['filter'], dict):
        raise BadSpecError(_('filter property must be a dictionary.'))

    filter = FilterFactory.from_spec(spec['filter'])
    display_name = spec.get('display_name', spec['column_id'])
    return BooleanIndicator(display_name, spec['column_id'], filter)


class IndicatorFactory(object):
    constructor_map = {
        'boolean': _build_boolean_indicator,
    }

    @classmethod
    def from_spec(cls, spec):
        cls.validate_spec(spec)
        return cls.constructor_map[spec['type']](spec)

    @classmethod
    def validate_spec(self, spec):
        if 'type' not in spec:
            raise BadSpecError(_('Indicator specification must include a root level type field.'))
        elif spec['type'] not in self.constructor_map:
            raise BadSpecError(_('Illegal indicator type: "{0}", must be one of the following choice: ({1})'.format(
                spec['type'],
                ', '.join(self.constructor_map.keys())
            )))

def _validate_required_fields(spec, fields):
    for key in fields:
        if not spec.get(key):
            raise BadSpecError(_('Spec must include a valid "{0}" field.'.format(key)))
