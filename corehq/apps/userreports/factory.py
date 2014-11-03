import json
from django.utils.translation import ugettext as _
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.specs import RawIndicatorSpec, ChoiceListIndicatorSpec, BooleanIndicatorSpec, \
    IndicatorSpecBase, PropertyMatchFilterSpec, NotFilterSpec, NamedFilterSpec
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.filters import SinglePropertyValueFilter
from corehq.apps.userreports.indicators import BooleanIndicator, CompoundIndicator, RawIndicator, Column
from corehq.apps.userreports.logic import EQUAL
from fluff.filters import ANDFilter, ORFilter, CustomFilter, NOTFilter


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
    wrapped = PropertyMatchFilterSpec.wrap(spec)
    return SinglePropertyValueFilter(
        getter=wrapped.getter,
        operator=EQUAL,
        reference_value=wrapped.property_value,
    )


def _build_named_filter(spec, context):
    wrapped = NamedFilterSpec.wrap(spec)
    return context[wrapped.name]


class FilterFactory(object):
    constructor_map = {
        'property_match': _build_property_match_filter,
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
        except (AssertionError, BadValueError) as e:
            raise BadSpecError(_('Problem creating filter from spec: {}, message is {}').format(
                json.dumps(spec, indent=2),
                str(e),
            ))

    @classmethod
    def validate_spec(self, spec):
        _validate_required_fields(spec, ('type',))
        if spec['type'] not in self.constructor_map:
            raise BadSpecError(_('Illegal filter type: "{0}", must be one of the following choice: ({1})'.format(
                spec['type'],
                ', '.join(self.constructor_map.keys())
            )))


def _build_count_indicator(spec, context):
    wrapped = IndicatorSpecBase.wrap(spec)
    return BooleanIndicator(
        wrapped.display_name,
        wrapped.column_id,
        CustomFilter(lambda item: True),
    )


def _build_raw_indicator(spec, context):
    wrapped = RawIndicatorSpec.wrap(spec)
    column = Column(
        id=wrapped.column_id,
        datatype=wrapped.datatype,
        is_nullable=wrapped.is_nullable,
        is_primary_key=wrapped.is_primary_key,
    )
    return RawIndicator(
        wrapped.display_name,
        column,
        getter=wrapped.getter
    )


def _build_boolean_indicator(spec, context):
    wrapped = BooleanIndicatorSpec.wrap(spec)
    return BooleanIndicator(
        wrapped.display_name,
        wrapped.column_id,
        FilterFactory.from_spec(wrapped.filter, context),
    )


def _build_choice_list_indicator(spec, context):
    wrapped_spec = ChoiceListIndicatorSpec.wrap(spec)
    base_display_name = wrapped_spec.display_name

    def _construct_display(choice):
        return '{base} ({choice})'.format(base=base_display_name, choice=choice)

    def _construct_column(choice):
        return '{col}_{choice}'.format(col=spec['column_id'], choice=choice)

    choice_indicators = [
        BooleanIndicator(
            display_name=_construct_display(choice),
            column_id=_construct_column(choice),
            filter=SinglePropertyValueFilter(
                getter=wrapped_spec.getter,
                operator=wrapped_spec.get_operator(),
                reference_value=choice,
            )
        ) for choice in spec['choices']
    ]
    return CompoundIndicator(base_display_name, choice_indicators)


class IndicatorFactory(object):
    constructor_map = {
        'count': _build_count_indicator,
        'boolean': _build_boolean_indicator,
        'raw': _build_raw_indicator,
        'choice_list': _build_choice_list_indicator,
    }

    @classmethod
    def from_spec(cls, spec, context=None):
        cls.validate_spec(spec)
        try:
            return cls.constructor_map[spec['type']](spec, context)
        except BadValueError, e:
            # for now reraise jsonobject exceptions as BadSpecErrors
            raise BadSpecError(str(e))

    @classmethod
    def validate_spec(self, spec):
        if 'type' not in spec:
            raise BadSpecError(_('Indicator specification must include a root level type field.'))
        elif spec['type'] not in self.constructor_map:
            raise BadSpecError(
                _('Illegal indicator type: "{0}", must be one of the following choice: ({1})'.format(
                    spec['type'],
                    ', '.join(self.constructor_map.keys())
                ))
            )


def _validate_required_fields(spec, fields):
    for key in fields:
        if not spec.get(key):
            raise BadSpecError(_('Spec must include a valid "{0}" field.'.format(key)))
