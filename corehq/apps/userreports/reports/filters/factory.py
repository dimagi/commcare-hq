from __future__ import absolute_import
from __future__ import unicode_literals
import json
from jsonobject.exceptions import BadValueError
from corehq.apps.reports_core.filters import DatespanFilter, ChoiceListFilter, Choice, DynamicChoiceListFilter, \
    NumericFilter, PreFilter, QuarterFilter, LocationDrilldownFilter, MultiFieldDynamicChoiceListFilter
from corehq.apps.userreports.exceptions import BadSpecError
from django.utils.translation import ugettext as _
from corehq.apps.userreports.reports.filters.choice_providers import DATA_SOURCE_COLUMN, \
    LOCATION, DataSourceColumnChoiceProvider, LocationChoiceProvider, UserChoiceProvider, \
    USER, OWNER, OwnerChoiceProvider, MultiFieldDataSourceColumnChoiceProvider
from corehq.apps.userreports.reports.filters.values import (
    dynamic_choice_list_url,
    NONE_CHOICE,
    SHOW_ALL_CHOICE,
)
from corehq.apps.userreports.reports.filters.specs import (
    ChoiceListFilterSpec, DynamicChoiceListFilterSpec, NumericFilterSpec, DateFilterSpec,
    PreFilterSpec, QuarterFilterSpec, LocationDrilldownFilterSpec, MultiFieldDynamicChoiceFilterSpec)


def _build_date_filter(spec, report):
    wrapped = DateFilterSpec.wrap(spec)
    return DatespanFilter(
        name=wrapped.slug,
        label=wrapped.get_display(),
        compare_as_string=wrapped.compare_as_string,
    )


def _build_quarter_filter(spec, report):
    wrapped = QuarterFilterSpec.wrap(spec)
    return QuarterFilter(
        name=wrapped.slug,
        label=wrapped.get_display(),
        show_all=wrapped.show_all,
    )


def _build_numeric_filter(spec, report):
    wrapped = NumericFilterSpec.wrap(spec)
    return NumericFilter(
        name=wrapped.slug,
        label=wrapped.get_display(),
    )


def _build_pre_filter(spec, report):
    wrapped = PreFilterSpec.wrap(spec)
    return PreFilter(
        name=wrapped.slug,
        datatype=wrapped.datatype,
        pre_value=wrapped.pre_value,
        pre_operator=wrapped.pre_operator,
    )


def _build_choice_list_filter(spec, report):
    wrapped = ChoiceListFilterSpec.wrap(spec)
    choices = [Choice(
        fc.value if fc.value is not None else NONE_CHOICE,
        fc.get_display()
    ) for fc in wrapped.choices]
    if wrapped.show_all:
        choices.insert(0, Choice(SHOW_ALL_CHOICE, _('Show all')))
    return ChoiceListFilter(
        name=wrapped.slug,
        field=wrapped.field,
        datatype=wrapped.datatype,
        label=wrapped.display,
        choices=choices,
    )


def _build_dynamic_choice_list_filter(spec, report):
    wrapped = DynamicChoiceListFilterSpec.wrap(spec)
    choice_provider_spec = wrapped.get_choice_provider_spec()
    choice_provider = FilterChoiceProviderFactory.from_spec(choice_provider_spec)(report, wrapped.slug)
    choice_provider.configure(choice_provider_spec)

    invalid_spec = (
        wrapped.ancestor_expression and
        not set(wrapped.ancestor_expression.keys()) == set(['field', 'location_type'])
    )
    if invalid_spec:
        raise BadSpecError(_(
            "'ancestor_expression' must be empty dictionary or have 'field', 'location_type' keys"))

    if wrapped.ancestor_expression and not isinstance(choice_provider, LocationChoiceProvider):
        raise BadSpecError(_(
            "'ancestor_expression' is applicable only for location choices"
        ))

    return DynamicChoiceListFilter(
        name=wrapped.slug,
        datatype=wrapped.datatype,
        field=wrapped.field,
        label=wrapped.display,
        show_all=wrapped.show_all,
        url_generator=dynamic_choice_list_url,
        choice_provider=choice_provider,
        ancestor_expression=wrapped.ancestor_expression,
    )


def _build_multi_field_dynamic_choice_list_filter(spec, report):
    wrapped = MultiFieldDynamicChoiceFilterSpec.wrap(spec)
    choice_provider_spec = wrapped.get_choice_provider_spec()
    choice_provider = MultiFieldChoiceProviderFactory.from_spec(choice_provider_spec)(report, wrapped.slug)
    choice_provider.configure(choice_provider_spec)
    return MultiFieldDynamicChoiceListFilter(
        name=wrapped.slug,
        datatype=wrapped.datatype,
        fields=wrapped.fields,
        label=wrapped.display,
        show_all=wrapped.show_all,
        url_generator=dynamic_choice_list_url,
        choice_provider=choice_provider,
    )


def _build_location_drilldown_filter(spec, report):
    wrapped = LocationDrilldownFilterSpec.wrap(spec)

    valid_spec = (
        not wrapped.ancestor_expression or
        set(wrapped.ancestor_expression.keys()) == set(['field', 'location_type'])
    )
    if not valid_spec:
        raise BadSpecError(_(
            "'ancestor_expression' must be empty dictionary or have 'field', 'location_type' keys"))

    return LocationDrilldownFilter(
        name=wrapped.slug,
        datatype=wrapped.datatype,
        field=wrapped.field,
        label=wrapped.display,
        domain=report.domain,
        include_descendants=wrapped.include_descendants,
        max_drilldown_levels=wrapped.max_drilldown_levels,
        ancestor_expression=wrapped.ancestor_expression,
    )


class ReportFilterFactory(object):
    constructor_map = {
        'date': _build_date_filter,
        'quarter': _build_quarter_filter,
        'pre': _build_pre_filter,
        'choice_list': _build_choice_list_filter,
        'dynamic_choice_list': _build_dynamic_choice_list_filter,
        'multi_field_dynamic_choice_list': _build_multi_field_dynamic_choice_list_filter,
        'numeric': _build_numeric_filter,
        'location_drilldown': _build_location_drilldown_filter,
    }

    @classmethod
    def from_spec(cls, spec, report=None):
        cls.validate_spec(spec)
        try:
            return cls.constructor_map[spec['type']](spec, report)
        except (AssertionError, BadValueError) as e:
            raise BadSpecError(_('Problem creating report filter from spec: {}, message is: {}').format(
                json.dumps(spec, indent=2),
                str(e),
            ))

    @classmethod
    def validate_spec(cls, spec):
        if spec.get('type') not in cls.constructor_map:
            raise BadSpecError(
                _('Illegal report filter type: {0}, must be one of the following choice: ({1})').format(
                    spec.get('type', _('(missing from spec)')),
                    ', '.join(cls.constructor_map)
                )
            )


class FilterChoiceProviderFactory(object):
    constructor_map = {
        DATA_SOURCE_COLUMN: DataSourceColumnChoiceProvider,
        LOCATION: LocationChoiceProvider,
        USER: UserChoiceProvider,
        OWNER: OwnerChoiceProvider
    }

    @classmethod
    def from_spec(cls, choice_provider_spec):
        return cls.constructor_map.get(choice_provider_spec['type'], DataSourceColumnChoiceProvider)


class MultiFieldChoiceProviderFactory(FilterChoiceProviderFactory):
    constructor_map = {
        DATA_SOURCE_COLUMN: MultiFieldDataSourceColumnChoiceProvider,
        LOCATION: LocationChoiceProvider,
        USER: UserChoiceProvider,
        OWNER: OwnerChoiceProvider
    }
