from jsonobject import JsonObject, StringProperty, BooleanProperty, ListProperty, DictProperty
from jsonobject.base import DefaultProperty
from sqlagg import CountUniqueColumn, SumColumn
from sqlagg.columns import (
    MonthColumn,
    SimpleColumn,
    YearColumn,
)
from corehq.apps.reports.sqlreport import DatabaseColumn
from corehq.apps.userreports.indicators.specs import DataTypeProperty
from corehq.apps.userreports.reports.filters import DateFilterValue, ChoiceListFilterValue, \
    NumericFilterValue
from corehq.apps.userreports.specs import TypeProperty
from corehq.apps.userreports.transforms.factory import TransformFactory


SQLAGG_COLUMN_MAP = {
    'count_unique': CountUniqueColumn,
    'month': MonthColumn,
    'sum': SumColumn,
    'simple': SimpleColumn,
    'year': YearColumn,
}


class ReportFilter(JsonObject):
    type = StringProperty(required=True)
    slug = StringProperty(required=True)
    field = StringProperty(required=True)
    display = StringProperty()

    def create_filter_value(self, value):
        return {
            'date': DateFilterValue,
            'numeric': NumericFilterValue,
            'choice_list': ChoiceListFilterValue,
            'dynamic_choice_list': ChoiceListFilterValue,
        }[self.type](self, value)


class ReportColumn(JsonObject):
    type = StringProperty(required=True)
    display = StringProperty()
    description = StringProperty()
    field = StringProperty(required=True)
    aggregation = StringProperty(
        choices=SQLAGG_COLUMN_MAP.keys(),
        required=True,
    )
    alias = StringProperty()
    format = StringProperty(default='default', choices=[
        'default',
        'percent_of_total',
    ])
    transform = DictProperty()

    @property
    def report_column_id(self):
        return self.alias or self.field

    def get_format_fn(self):
        if self.transform:
            return TransformFactory.get_transform(self.transform).get_transform_function()
        return None

    def get_sql_column(self):
        return DatabaseColumn(
            self.display,
            SQLAGG_COLUMN_MAP[self.aggregation](self.field, alias=self.alias),
            sortable=False,
            data_slug=self.report_column_id,
            format_fn=self.get_format_fn(),
            help_text=self.description
        )


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
    display = StringProperty()
    required = BooleanProperty(default=False)

    def get_display(self):
        return self.display or self.slug


class ChoiceListFilterSpec(FilterSpec):
    type = TypeProperty('choice_list')
    show_all = BooleanProperty(default=True)
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
