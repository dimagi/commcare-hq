from django.utils.translation import ugettext as _
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions import ExpressionFactory
from corehq.apps.userreports.filters import SinglePropertyValueFilter, CustomFilter
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.indicators import (
    BooleanIndicator,
    Column,
    CompoundIndicator,
    LedgerBalancesIndicator,
    RawIndicator,
)
from corehq.apps.userreports.indicators.specs import (
    BooleanIndicatorSpec,
    ChoiceListIndicatorSpec,
    ExpressionIndicatorSpec,
    IndicatorSpecBase,
    LedgerBalancesIndicatorSpec,
    RawIndicatorSpec,
)


def _build_count_indicator(spec, context):
    wrapped = IndicatorSpecBase.wrap(spec)
    return BooleanIndicator(
        wrapped.display_name,
        wrapped.column_id,
        CustomFilter(lambda item, context=None: True),
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
                reference_expression=ExpressionFactory.from_spec(choice),
            )
        ) for choice in spec['choices']
    ]
    return CompoundIndicator(base_display_name, choice_indicators)


def _build_ledger_balances_indicator(spec, context):
    wrapped_spec = LedgerBalancesIndicatorSpec.wrap(spec)
    return LedgerBalancesIndicator(wrapped_spec)


def _build_repeat_iteration_indicator(spec, context):
    return RawIndicator(
        "base document iteration",
        Column(
            id="repeat_iteration",
            datatype="integer",
            is_nullable=False,
            is_primary_key=True,
        ),
        getter=lambda doc, ctx: ctx.iteration
    )


def _build_inserted_at(spec, context):
    return RawIndicator(
        "inserted at",
        Column(
            id="inserted_at",
            datatype="datetime",
            is_nullable=False,
            is_primary_key=False,
        ),
        getter=lambda doc, ctx: ctx.inserted_timestamp
    )


class IndicatorFactory(object):
    constructor_map = {
        'boolean': _build_boolean_indicator,
        'choice_list': _build_choice_list_indicator,
        'count': _build_count_indicator,
        'expression': _build_expression_indicator,
        'inserted_at': _build_inserted_at,
        'ledger_balances': _build_ledger_balances_indicator,
        'raw': _build_raw_indicator,
        'repeat_iteration': _build_repeat_iteration_indicator,
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
