from jsonobject import JsonObject, StringProperty
from sqlagg import SumColumn
from sqlagg.columns import SimpleColumn
from corehq.apps.reports.sqlreport import DatabaseColumn
from corehq.apps.reports_core.filters import DatespanFilter, ChoiceListFilter, Choice
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
from corehq.apps.userreports.reports.filters import DateFilterValue, ChoiceListFilterValue
from django.utils.translation import ugettext as _
from corehq.apps.userreports.reports.specs import FilterSpec, ChoiceListFilterSpec


def _build_date_filter(spec):
    wrapped = FilterSpec.wrap(spec)
    return DatespanFilter(
        name=wrapped.slug,
        label=wrapped.get_display(),
        required=wrapped.required,
    )


def _build_choice_list_filter(spec):
    wrapped = ChoiceListFilterSpec.wrap(spec)
    return ChoiceListFilter(
        name=wrapped.slug,
        label=wrapped.display,
        required=wrapped.required,
        choices=[Choice(fc.value, fc.get_display()) for fc in wrapped.choices]
    )


class ReportFilterFactory(object):
    constructor_map = {
        'date': _build_date_filter,
        'choice_list': _build_choice_list_filter,
    }

    @classmethod
    def from_spec(cls, spec):
        return cls.constructor_map[spec['type']](spec)

    @classmethod
    def validate_spec(self, spec):
        if spec['type'] not in self.constructor_map:
            raise BadSpecError(_('Illegal report filter type: "{0}", must be one of the following choice: ({1})'.format(
                spec['type'],
                ', '.join(self.constructor_map.keys())
            )))


class ReportFactory(object):

    @classmethod
    def from_spec(cls, spec):
        # todo: validation and what not
        return ConfigurableReportDataSource(
            domain=spec.domain,
            table_id=spec.table_id,
            filters=[ReportFilter.wrap(f) for f in spec.filters],
            aggregation_columns=spec.aggregation_columns,
            columns=[ReportColumn.wrap(colspec) for colspec in spec.columns],
        )


class ReportFilter(JsonObject):
    type = StringProperty(required=True)
    slug = StringProperty(required=True)
    field = StringProperty(required=True)
    display = StringProperty()

    def create_filter_value(self, value):
        return {
            'date': DateFilterValue,
            'choice_list': ChoiceListFilterValue,
        }[self.type](self, value)


class ReportColumn(JsonObject):
    type = StringProperty(required=True)
    display = StringProperty()
    field = StringProperty(required=True)
    aggregation = StringProperty(required=True)

    def get_sql_column(self):
        # todo: find a better home for this
        sqlagg_column_map = {
            'sum': SumColumn,
            'simple': SimpleColumn,
        }
        return DatabaseColumn(self.display, sqlagg_column_map[self.aggregation](self.field),
                              sortable=False, data_slug=self.field)

