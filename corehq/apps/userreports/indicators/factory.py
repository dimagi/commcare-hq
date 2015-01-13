from django.utils.translation import ugettext as _
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.filters import SinglePropertyValueFilter
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.indicators import BooleanIndicator, CompoundIndicator, RawIndicator, Column
from corehq.apps.userreports.indicators.specs import (RawIndicatorSpec, ChoiceListIndicatorSpec,
    BooleanIndicatorSpec, IndicatorSpecBase, ExpressionIndicatorSpec)
from fluff.filters import CustomFilter


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


def _build_expression_indicator(spec, context):
    wrapped = ExpressionIndicatorSpec.wrap(spec)
    column = Column(
        id=wrapped.column_id,
        datatype=wrapped.datatype,
        is_nullable=wrapped.is_nullable,
        is_primary_key=wrapped.is_primary_key,
    )
    return RawIndicator(
        wrapped.display_name,
        column,
        getter=wrapped.parsed_expression(context),
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
                expression=wrapped_spec.getter,
                operator=wrapped_spec.get_operator(),
                reference_value=choice,
            )
        ) for choice in spec['choices']
    ]
    return CompoundIndicator(base_display_name, choice_indicators)


class IndicatorFactory(object):
    constructor_map = {
        'boolean': _build_boolean_indicator,
        'choice_list': _build_choice_list_indicator,
        'count': _build_count_indicator,
        'expression': _build_expression_indicator,
        'raw': _build_raw_indicator,
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
