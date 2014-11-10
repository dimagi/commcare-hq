import json
from jsonobject.exceptions import BadValueError
from corehq.apps.reports_core.filters import DatespanFilter, ChoiceListFilter, Choice, DynamicChoiceListFilter
from corehq.apps.userreports.exceptions import BadSpecError
from django.utils.translation import ugettext as _
from corehq.apps.userreports.reports.filters import SHOW_ALL_CHOICE, dynamic_choice_list_url
from corehq.apps.userreports.reports.specs import FilterSpec, ChoiceListFilterSpec, PieChartSpec, \
    MultibarAggregateChartSpec, MultibarChartSpec, ReportFilter, ReportColumn, DynamicChoiceListFilterSpec


def _build_date_filter(spec):
    wrapped = FilterSpec.wrap(spec)
    return DatespanFilter(
        name=wrapped.slug,
        label=wrapped.get_display(),
        required=wrapped.required,
    )


def _build_choice_list_filter(spec):
    wrapped = ChoiceListFilterSpec.wrap(spec)
    choices = [Choice(fc.value, fc.get_display()) for fc in wrapped.choices]
    if wrapped.show_all:
        choices.insert(0, Choice(SHOW_ALL_CHOICE, _('Show all')))
    return ChoiceListFilter(
        name=wrapped.slug,
        label=wrapped.display,
        required=wrapped.required,
        choices=choices,
    )


def _build_dynamic_choice_list_filter(spec):
    wrapped = DynamicChoiceListFilterSpec.wrap(spec)
    return DynamicChoiceListFilter(
        name=wrapped.slug,
        label=wrapped.display,
        required=wrapped.required,
        show_all=wrapped.show_all,
        url_generator=dynamic_choice_list_url,
    )


class ReportFilterFactory(object):
    constructor_map = {
        'date': _build_date_filter,
        'choice_list': _build_choice_list_filter,
        'dynamic_choice_list': _build_dynamic_choice_list_filter,
    }

    @classmethod
    def from_spec(cls, spec):
        cls.validate_spec(spec)
        try:
            return cls.constructor_map[spec['type']](spec)
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
                    ', '.join(cls.constructor_map.keys())
                )
            )


class ReportFactory(object):

    @classmethod
    def from_spec(cls, spec):
        from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
        return ConfigurableReportDataSource(
            domain=spec.domain,
            config_or_config_id=spec.config_id,
            filters=[ReportFilter.wrap(f) for f in spec.filters],
            aggregation_columns=spec.aggregation_columns,
            columns=[ReportColumn.wrap(colspec) for colspec in spec.columns],
        )


class ChartFactory(object):
    spec_map = {
        'pie': PieChartSpec,
        'multibar': MultibarChartSpec,
        'multibar-aggregate': MultibarAggregateChartSpec,
    }

    @classmethod
    def from_spec(cls, spec):
        if spec.get('type') not in cls.spec_map:
            raise BadSpecError(_('Illegal chart type: {0}, must be one of the following choice: ({1})').format(
                spec.get('type', _('(missing from spec)')),
                ', '.join(cls.spec_map.keys())
            ))
        try:
            return cls.spec_map[spec['type']].wrap(spec)
        except BadValueError as e:
            raise BadSpecError(_('Problem creating chart from spec: {}, message is: {}').format(
                json.dumps(spec, indent=2),
                str(e),
            ))
