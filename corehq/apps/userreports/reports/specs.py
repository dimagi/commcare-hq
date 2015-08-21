import json
from django.utils.translation import ugettext as _
from corehq.apps.userreports.reports.sorting import ASCENDING, DESCENDING
from dimagi.ext.jsonobject import JsonObject, StringProperty, BooleanProperty, ListProperty, DictProperty, ObjectProperty
from jsonobject.base import DefaultProperty
from sqlagg import CountUniqueColumn, SumColumn, CountColumn, MinColumn, MaxColumn, MeanColumn
from sqlagg.columns import (
    MonthColumn,
    SimpleColumn,
    YearColumn,
)
from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn
from corehq.apps.userreports.indicators.specs import DataTypeProperty
from corehq.apps.userreports.reports.filters import DateFilterValue, ChoiceListFilterValue, \
    NumericFilterValue
from corehq.apps.userreports.specs import TypeProperty
from corehq.apps.userreports.sql import get_expanded_column_config, SqlColumnConfig
from corehq.apps.userreports.transforms.factory import TransformFactory
from corehq.apps.userreports.util import localize


SQLAGG_COLUMN_MAP = {
    'avg': MeanColumn,
    'count_unique': CountUniqueColumn,
    'count': CountColumn,
    'min': MinColumn,
    'max': MaxColumn,
    'month': MonthColumn,
    'sum': SumColumn,
    'simple': SimpleColumn,
    'year': YearColumn,
}


class ReportFilter(JsonObject):
    type = StringProperty(required=True)
    slug = StringProperty(required=True)
    field = StringProperty(required=True)
    display = DefaultProperty()
    compare_as_string = BooleanProperty(default=False)

    def create_filter_value(self, value):
        return {
            'date': DateFilterValue,
            'numeric': NumericFilterValue,
            'choice_list': ChoiceListFilterValue,
            'dynamic_choice_list': ChoiceListFilterValue,
        }[self.type](self, value)


class ReportColumn(JsonObject):
    type = StringProperty(required=True)
    column_id = StringProperty(required=True)
    display = DefaultProperty()
    description = StringProperty()
    transform = DictProperty()

    def format_data(self, data):
        """
        Subclasses can apply formatting to the entire dataset.
        """
        pass

    def get_sql_column_config(self, data_source_config, lang):
        raise NotImplementedError('subclasses must override this')

    def get_format_fn(self):
        """
        A function that gets applied to the data just in time before the report is rendered.
        """
        if self.transform:
            return TransformFactory.get_transform(self.transform).get_transform_function()
        return None

    def get_group_by_columns(self):
        raise NotImplementedError(_("You can't group by columns of type {}".format(self.type)))

    def get_header(self, lang):
        return localize(self.display, lang)

    def get_column_ids(self):
        """
        Used as an abstraction layer for columns that can contain more than one data column
        (for example, PercentageColumns).
        """
        return [self.column_id]


class FieldColumn(ReportColumn):
    type = TypeProperty('field')
    field = StringProperty(required=True)
    aggregation = StringProperty(
        choices=SQLAGG_COLUMN_MAP.keys(),
        required=True,
    )
    format = StringProperty(default='default', choices=[
        'default',
        'percent_of_total',
    ])

    @classmethod
    def wrap(cls, obj):
        # lazy migrations for legacy data.
        # todo: remove once all reports are on new format
        # 1. set column_id to alias, or field if no alias found
        _add_column_id_if_missing(obj)
        # 2. if aggregation='expand' convert to ExpandedColumn
        if obj.get('aggregation') == 'expand':
            del obj['aggregation']
            obj['type'] = 'expanded'
            return ExpandedColumn.wrap(obj)

        return super(FieldColumn, cls).wrap(obj)

    def format_data(self, data):
        if self.format == 'percent_of_total':
            column_name = self.column_id
            total = sum(row[column_name] for row in data)
            for row in data:
                row[column_name] = '{:.0%}'.format(
                    float(row[column_name]) / total
                )

    def get_sql_column_config(self, data_source_config, lang):
        return SqlColumnConfig(columns=[
            DatabaseColumn(
                header=self.get_header(lang),
                agg_column=SQLAGG_COLUMN_MAP[self.aggregation](self.field, alias=self.column_id),
                sortable=False,
                data_slug=self.column_id,
                format_fn=self.get_format_fn(),
                help_text=self.description
            )
        ])

    def get_group_by_columns(self):
        return [self.column_id]


class ExpandedColumn(ReportColumn):
    type = TypeProperty('expanded')
    field = StringProperty(required=True)

    @classmethod
    def wrap(cls, obj):
        # lazy migrations for legacy data.
        # todo: remove once all reports are on new format
        _add_column_id_if_missing(obj)
        return super(ExpandedColumn, cls).wrap(obj)

    def get_sql_column_config(self, data_source_config, lang):
        return get_expanded_column_config(data_source_config, self, lang)


class AggregateDateColumn(ReportColumn):
    """
    Used for grouping months and years together.
    """
    type = TypeProperty('aggregate_date')
    field = StringProperty(required=True)

    def get_sql_column_config(self, data_source_config, lang):
        return SqlColumnConfig(columns=[
            AggregateColumn(
                header=self.get_header(lang),
                aggregate_fn=lambda year, month: {'year': year, 'month': month},
                format_fn=self.get_format_fn(),
                columns=[
                    YearColumn(self.field, alias=self._year_column_alias()),
                    MonthColumn(self.field, alias=self._month_column_alias()),
                ],
                slug=self.column_id,
                data_slug=self.column_id,
            )],
        )

    def _year_column_alias(self):
        return '{}_year'.format(self.column_id)

    def _month_column_alias(self):
        return '{}_month'.format(self.column_id)

    def get_format_fn(self):
        # todo: support more aggregation/more formats
        return lambda data: '{}-{:02d}'.format(int(data['year']), int(data['month']))

    def get_group_by_columns(self):
        return [self._year_column_alias(), self._month_column_alias()]


class PercentageColumn(ReportColumn):
    type = TypeProperty('percent')
    numerator = ObjectProperty(FieldColumn, required=True)
    denominator = ObjectProperty(FieldColumn, required=True)
    format = StringProperty(
        choices=['percent', 'fraction', 'both', 'numeric_percent', 'decimal'],
        default='percent'
    )

    def get_sql_column_config(self, data_source_config, lang):
        # todo: better checks that fields are not expand
        num_config = self.numerator.get_sql_column_config(data_source_config, lang)
        denom_config = self.denominator.get_sql_column_config(data_source_config, lang)
        return SqlColumnConfig(columns=[
            AggregateColumn(
                header=self.get_header(lang),
                aggregate_fn=lambda n, d: {'num': n, 'denom': d},
                format_fn=self.get_format_fn(),
                columns=[c.view for c in num_config.columns + denom_config.columns],
                slug=self.column_id,
                data_slug=self.column_id,
            )],
            warnings=num_config.warnings + denom_config.warnings,
        )

    def get_format_fn(self):
        NO_DATA_TEXT = '--'
        CANT_CALCULATE_TEXT = '?'

        class NoData(Exception):
            pass

        class BadData(Exception):
            pass

        def trap_errors(fn):
            def inner(*args, **kwargs):
                try:
                    return fn(*args, **kwargs)
                except BadData:
                    return CANT_CALCULATE_TEXT
                except NoData:
                    return NO_DATA_TEXT
            return inner

        def _raw(data):
            if data['denom']:
                try:
                    return round(float(data['num']) / float(data['denom']), 3)
                except (ValueError, TypeError):
                    raise BadData()
            else:
                raise NoData()

        def _raw_pct(data, round_type=float):
            return round_type(_raw(data) * 100)

        @trap_errors
        def _clean_raw(data):
            return _raw(data)

        @trap_errors
        def _numeric_pct(data):
            return _raw_pct(data, round_type=int)

        @trap_errors
        def _pct(data):
            return '{0:.0f}%'.format(_raw_pct(data))

        _fraction = lambda data: '{num}/{denom}'.format(**data)

        return {
            'percent': _pct,
            'fraction': _fraction,
            'both': lambda data: '{} ({})'.format(_pct(data), _fraction(data)),
            'numeric_percent': _numeric_pct,
            'decimal': _clean_raw,
        }[self.format]

    def get_column_ids(self):
        # override this to include the columns for the numerator and denominator as well
        return [self.column_id, self.numerator.column_id, self.denominator.column_id]


def _add_column_id_if_missing(obj):
    if obj.get('column_id') is None:
        obj['column_id'] = obj.get('alias') or obj['field']


class FilterChoice(JsonObject):
    value = DefaultProperty()
    display = StringProperty()

    def get_display(self):
        return self.display or self.value


class FilterSpec(JsonObject):
    """
    This is the spec for a report filter - a thing that should show up as a UI filter element
    in a report (like a date picker or a select list).
    """
    type = StringProperty(required=True, choices=['date', 'numeric', 'choice_list', 'dynamic_choice_list'])
    slug = StringProperty(required=True)  # this shows up as the ID in the filter HTML
    field = StringProperty(required=True)  # this is the actual column that is queried
    display = DefaultProperty()
    required = BooleanProperty(default=False)
    datatype = DataTypeProperty(default='string')

    def get_display(self):
        return self.display or self.slug


class DateFilterSpec(FilterSpec):
    compare_as_string = BooleanProperty(default=False)


class ChoiceListFilterSpec(FilterSpec):
    type = TypeProperty('choice_list')
    show_all = BooleanProperty(default=True)
    datatype = DataTypeProperty(default='string')
    choices = ListProperty(FilterChoice)


class DynamicChoiceListFilterSpec(FilterSpec):
    type = TypeProperty('dynamic_choice_list')
    show_all = BooleanProperty(default=True)
    datatype = DataTypeProperty(default='string')

    @property
    def choices(self):
        return []


class NumericFilterSpec(FilterSpec):
    type = TypeProperty('numeric')


class ChartSpec(JsonObject):
    type = StringProperty(required=True)
    title = StringProperty()
    chart_id = StringProperty()

    @classmethod
    def wrap(cls, obj):
        if obj.get('chart_id') is None:
            obj['chart_id'] = (obj.get('title') or '') + str(hash(json.dumps(sorted(obj.items()))))
        return super(ChartSpec, cls).wrap(obj)


class PieChartSpec(ChartSpec):
    type = TypeProperty('pie')
    aggregation_column = StringProperty()
    value_column = StringProperty(required=True)


class MultibarChartSpec(ChartSpec):
    type = TypeProperty('multibar')
    aggregation_column = StringProperty()
    x_axis_column = StringProperty(required=True)
    y_axis_columns = ListProperty(unicode)
    is_stacked = BooleanProperty(default=False)


class MultibarAggregateChartSpec(ChartSpec):
    type = TypeProperty('multibar-aggregate')
    primary_aggregation = StringProperty(required=True)
    secondary_aggregation = StringProperty(required=True)
    value_column = StringProperty(required=True)


class OrderBySpec(JsonObject):
    field = StringProperty()
    order = StringProperty(choices=[ASCENDING, DESCENDING], default=ASCENDING)
