import datetime
import functools
import json

from django.utils.translation import gettext as _

from jsonobject.exceptions import BadValueError

from corehq.apps.userreports.specs import FactoryContext
from dimagi.utils.parsing import json_format_date, json_format_datetime
from dimagi.utils.web import json_handler

from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.date_specs import (
    AddDaysExpressionSpec,
    AddMonthsExpressionSpec,
    DiffDaysExpressionSpec,
    EthiopianDateToGregorianDateSpec,
    GregorianDateToEthiopianDateSpec,
    MonthEndDateExpressionSpec,
    MonthStartDateExpressionSpec,
    AddHoursExpressionSpec,
    UTCNow
)
from corehq.apps.userreports.expressions.list_specs import (
    FilterItemsExpressionSpec,
    FlattenExpressionSpec,
    MapItemsExpressionSpec,
    ReduceItemsExpressionSpec,
    SortItemsExpressionSpec,
)
from corehq.apps.userreports.expressions.specs import (
    ArrayIndexExpressionSpec,
    CaseSharingGroupsExpressionSpec,
    CoalesceExpressionSpec,
    ConditionalExpressionSpec,
    ConstantGetterSpec,
    DictExpressionSpec,
    EvalExpressionSpec,
    FormsExpressionSpec,
    IdentityExpressionSpec,
    IterationNumberExpressionSpec,
    IteratorExpressionSpec,
    JsonpathExpressionSpec,
    NamedExpressionSpec,
    NestedExpressionSpec,
    PropertyNameGetterSpec,
    PropertyPathGetterSpec,
    RelatedDocExpressionSpec,
    ReportingGroupsExpressionSpec,
    RootDocExpressionSpec,
    SplitStringExpressionSpec,
    SubcasesExpressionSpec,
    SwitchExpressionSpec,
)


def _make_filter(spec, factory_context):
    # just pulled out here to keep the inline imports to a minimum
    # no way around this since the two factories inherently depend on each other
    from corehq.apps.userreports.filters.factory import FilterFactory
    return FilterFactory.from_spec(spec, factory_context)


def _simple_expression_generator(wrapper_class, spec, factory_context):
    return wrapper_class.wrap(spec)


_identity_expression = functools.partial(_simple_expression_generator, IdentityExpressionSpec)
_constant_expression = functools.partial(_simple_expression_generator, ConstantGetterSpec)
_property_name_expression = functools.partial(_simple_expression_generator, PropertyNameGetterSpec)
_property_path_expression = functools.partial(_simple_expression_generator, PropertyPathGetterSpec)
_iteration_number_expression = functools.partial(_simple_expression_generator, IterationNumberExpressionSpec)
_jsonpath_expression = functools.partial(_simple_expression_generator, JsonpathExpressionSpec)
_utcnow = functools.partial(_simple_expression_generator, UTCNow)


def _property_name_expression(spec, factory_context):
    expression = PropertyNameGetterSpec.wrap(spec)
    expression.configure(
        ExpressionFactory.from_spec(expression.property_name, factory_context)
    )
    return expression


def _named_expression(spec, factory_context):
    expression = NamedExpressionSpec.wrap(spec)
    expression.configure(factory_context)
    return expression


def _conditional_expression(spec, factory_context):
    wrapped = ConditionalExpressionSpec.wrap(spec)
    wrapped.configure(
        _make_filter(wrapped.test, factory_context),
        ExpressionFactory.from_spec(wrapped.expression_if_true, factory_context),
        ExpressionFactory.from_spec(wrapped.expression_if_false, factory_context),
    )
    return wrapped


def _switch_expression(spec, factory_context):
    wrapped = SwitchExpressionSpec.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.switch_on, factory_context),
        {k: ExpressionFactory.from_spec(v, factory_context) for k, v in wrapped.cases.items()},
        ExpressionFactory.from_spec(wrapped.default, factory_context),
    )
    return wrapped


def _array_index_expression(spec, factory_context):
    wrapped = ArrayIndexExpressionSpec.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.array_expression, factory_context),
        ExpressionFactory.from_spec(wrapped.index_expression, factory_context),
    )
    return wrapped


def _root_doc_expression(spec, factory_context):
    wrapped = RootDocExpressionSpec.wrap(spec)
    wrapped.configure(ExpressionFactory.from_spec(wrapped.expression, factory_context))
    return wrapped


def _related_doc_expression(spec, factory_context):
    wrapped = RelatedDocExpressionSpec.wrap(spec)
    wrapped.configure(
        doc_id_expression=ExpressionFactory.from_spec(wrapped.doc_id_expression, factory_context),
        value_expression=ExpressionFactory.from_spec(wrapped.value_expression, factory_context),
    )
    return wrapped


def _iterator_expression(spec, factory_context):
    wrapped = IteratorExpressionSpec.wrap(spec)
    wrapped.configure(
        expressions=[ExpressionFactory.from_spec(e, factory_context) for e in wrapped.expressions],
        test=_make_filter(wrapped.test, factory_context) if wrapped.test else None
    )
    return wrapped


def _nested_expression(spec, factory_context):
    wrapped = NestedExpressionSpec.wrap(spec)
    wrapped.configure(
        argument_expression=ExpressionFactory.from_spec(wrapped.argument_expression, factory_context),
        value_expression=ExpressionFactory.from_spec(wrapped.value_expression, factory_context),
    )
    return wrapped


def _dict_expression(spec, factory_context):
    wrapped = DictExpressionSpec.wrap(spec)
    compiled_properties = {
        key: ExpressionFactory.from_spec(value, factory_context)
        for key, value in wrapped.properties.items()
    }
    wrapped.configure(compiled_properties=compiled_properties)
    return wrapped


def _add_days_expression(spec, factory_context):
    wrapped = AddDaysExpressionSpec.wrap(spec)
    wrapped.configure(
        date_expression=ExpressionFactory.from_spec(wrapped.date_expression, factory_context),
        count_expression=ExpressionFactory.from_spec(wrapped.count_expression, factory_context),
    )
    return wrapped


def _add_hours_expression(spec, factory_context):
    wrapped = AddHoursExpressionSpec.wrap(spec)
    wrapped.configure(
        date_expression=ExpressionFactory.from_spec(wrapped.date_expression, factory_context),
        count_expression=ExpressionFactory.from_spec(wrapped.count_expression, factory_context),
    )
    return wrapped


def _add_months_expression(spec, factory_context):
    wrapped = AddMonthsExpressionSpec.wrap(spec)
    wrapped.configure(
        date_expression=ExpressionFactory.from_spec(wrapped.date_expression, factory_context),
        months_expression=ExpressionFactory.from_spec(wrapped.months_expression, factory_context),
    )
    return wrapped


def _month_start_date_expression(spec, factory_context):
    wrapped = MonthStartDateExpressionSpec.wrap(spec)
    wrapped.configure(
        date_expression=ExpressionFactory.from_spec(wrapped.date_expression, factory_context),
    )
    return wrapped


def _month_end_date_expression(spec, factory_context):
    wrapped = MonthEndDateExpressionSpec.wrap(spec)
    wrapped.configure(
        date_expression=ExpressionFactory.from_spec(wrapped.date_expression, factory_context),
    )
    return wrapped


def _diff_days_expression(spec, factory_context):
    wrapped = DiffDaysExpressionSpec.wrap(spec)
    wrapped.configure(
        from_date_expression=ExpressionFactory.from_spec(wrapped.from_date_expression, factory_context),
        to_date_expression=ExpressionFactory.from_spec(wrapped.to_date_expression, factory_context),
    )
    return wrapped


def _gregorian_date_to_ethiopian_date(spec, factory_context):
    wrapped = GregorianDateToEthiopianDateSpec.wrap(spec)
    wrapped.configure(
        date_expression=ExpressionFactory.from_spec(wrapped.date_expression, factory_context),
    )
    return wrapped


def _ethiopian_date_to_gregorian_date(spec, factory_context):
    wrapped = EthiopianDateToGregorianDateSpec.wrap(spec)
    wrapped.configure(
        date_expression=ExpressionFactory.from_spec(wrapped.date_expression, factory_context),
    )
    return wrapped


def _evaluator_expression(spec, factory_context):
    wrapped = EvalExpressionSpec.wrap(spec)
    wrapped.configure(factory_context)
    return wrapped


def _get_forms_expression(spec, factory_context):
    wrapped = FormsExpressionSpec.wrap(spec)
    wrapped.configure(
        case_id_expression=ExpressionFactory.from_spec(wrapped.case_id_expression, factory_context)
    )
    return wrapped


def _get_subcases_expression(spec, factory_context):
    wrapped = SubcasesExpressionSpec.wrap(spec)
    wrapped.configure(
        case_id_expression=ExpressionFactory.from_spec(wrapped.case_id_expression, factory_context)
    )
    return wrapped


def _get_case_sharing_groups_expression(spec, factory_context):
    wrapped = CaseSharingGroupsExpressionSpec.wrap(spec)
    wrapped.configure(
        user_id_expression=ExpressionFactory.from_spec(wrapped.user_id_expression, factory_context)
    )
    return wrapped


def _get_reporting_groups_expression(spec, factory_context):
    wrapped = ReportingGroupsExpressionSpec.wrap(spec)
    wrapped.configure(
        user_id_expression=ExpressionFactory.from_spec(wrapped.user_id_expression, factory_context)
    )
    return wrapped


def _filter_items_expression(spec, factory_context):
    wrapped = FilterItemsExpressionSpec.wrap(spec)
    wrapped.configure(
        items_expression=ExpressionFactory.from_spec(wrapped.items_expression, factory_context),
        filter_expression=_make_filter(wrapped.filter_expression, factory_context)
    )
    return wrapped


def _map_items_expression(spec, factory_context):
    wrapped = MapItemsExpressionSpec.wrap(spec)
    wrapped.configure(
        items_expression=ExpressionFactory.from_spec(wrapped.items_expression, factory_context),
        map_expression=ExpressionFactory.from_spec(wrapped.map_expression, factory_context)
    )
    return wrapped


def _reduce_items_expression(spec, factory_context):
    wrapped = ReduceItemsExpressionSpec.wrap(spec)
    wrapped.configure(
        items_expression=ExpressionFactory.from_spec(wrapped.items_expression, factory_context)
    )
    return wrapped


def _flatten_expression(spec, factory_context):
    wrapped = FlattenExpressionSpec.wrap(spec)
    wrapped.configure(
        items_expression=ExpressionFactory.from_spec(wrapped.items_expression, factory_context)
    )
    return wrapped


def _sort_items_expression(spec, factory_context):
    wrapped = SortItemsExpressionSpec.wrap(spec)
    wrapped.configure(
        items_expression=ExpressionFactory.from_spec(wrapped.items_expression, factory_context),
        sort_expression=ExpressionFactory.from_spec(wrapped.sort_expression, factory_context)
    )
    return wrapped


def _split_string_expression(spec, factory_context):
    wrapped = SplitStringExpressionSpec.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.string_expression, factory_context),
        ExpressionFactory.from_spec(wrapped.index_expression, factory_context),
    )
    return wrapped


def _coalesce_expression(spec, factory_context):
    wrapped = CoalesceExpressionSpec.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.expression, factory_context),
        ExpressionFactory.from_spec(wrapped.default_expression, factory_context),
    )
    return wrapped


class ExpressionFactory(object):
    spec_map = {
        'add_days': _add_days_expression,
        'add_hours': _add_hours_expression,
        'add_months': _add_months_expression,
        'array_index': _array_index_expression,
        'base_iteration_number': _iteration_number_expression,
        'coalesce': _coalesce_expression,
        'conditional': _conditional_expression,
        'constant': _constant_expression,
        'dict': _dict_expression,
        'diff_days': _diff_days_expression,
        'ethiopian_date_to_gregorian_date': _ethiopian_date_to_gregorian_date,
        'evaluator': _evaluator_expression,
        'filter_items': _filter_items_expression,
        'flatten': _flatten_expression,
        'get_case_forms': _get_forms_expression,
        'get_case_sharing_groups': _get_case_sharing_groups_expression,
        'get_reporting_groups': _get_reporting_groups_expression,
        'get_subcases': _get_subcases_expression,
        'gregorian_date_to_ethiopian_date': _gregorian_date_to_ethiopian_date,
        'identity': _identity_expression,
        'iterator': _iterator_expression,
        'jsonpath': _jsonpath_expression,
        'map_items': _map_items_expression,
        'month_end_date': _month_end_date_expression,
        'month_start_date': _month_start_date_expression,
        'named': _named_expression,
        'nested': _nested_expression,
        'property_name': _property_name_expression,
        'property_path': _property_path_expression,
        'reduce_items': _reduce_items_expression,
        'related_doc': _related_doc_expression,
        'root_doc': _root_doc_expression,
        'sort_items': _sort_items_expression,
        'split_string': _split_string_expression,
        'switch': _switch_expression,
        'utcnow': _utcnow,
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
    def from_spec(cls, spec, factory_context=None):
        factory_context = factory_context or FactoryContext.empty()
        if _is_literal(spec):
            return cls.from_spec(_convert_constant_to_expression_spec(spec), factory_context)
        try:
            return cls.spec_map[spec['type']](spec, factory_context)
        except KeyError:
            raise BadSpecError(_('Invalid or missing expression type: {} for expression: {}. '
                                 'Valid options are: {}').format(
                spec.get('type', '[missing]'),
                spec,
                ', '.join(cls.spec_map),
            ))
        except (TypeError, BadValueError) as e:
            raise BadSpecError(_('Problem creating expression: {}. Message is: {}').format(
                json.dumps(spec, indent=2, default=json_handler),
                str(e),
            ))


def _is_literal(value):
    return not isinstance(value, dict)


def _convert_constant_to_expression_spec(value):
    # this is a hack to reconvert these to json-strings in case they were already
    # converted to dates (e.g. because this was a sub-part of a filter or expression)
    if isinstance(value, datetime.datetime):
        value = json_format_datetime(value)
    elif isinstance(value, datetime.date):
        value = json_format_date(value)
    return {'type': 'constant', 'constant': value}
