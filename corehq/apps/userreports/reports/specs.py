from jsonobject import JsonObject, StringProperty, BooleanProperty, ListProperty
from jsonobject.base import DefaultProperty
from sqlagg import SumColumn
from sqlagg.columns import SimpleColumn
from corehq.apps.reports.sqlreport import DatabaseColumn
from corehq.apps.userreports.reports.filters import DateFilterValue, ChoiceListFilterValue
from corehq.apps.userreports.specs import TypeProperty


class ReportFilter(JsonObject):
    type = StringProperty(required=True)
    slug = StringProperty(required=True)
    field = StringProperty(required=True)
    display = StringProperty()

    def create_filter_value(self, value):
        return {
            'date': DateFilterValue,
            'choice_list': ChoiceListFilterValue,
            'dynamic_choice_list': ChoiceListFilterValue,
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


class FilterChoice(JsonObject):
    value = DefaultProperty(required=True)
    display = StringProperty()

    def get_display(self):
        return self.display or self.value


class FilterSpec(JsonObject):
    """
    This is the spec for a report filter - a thing that should show up as a UI filter element
    in a report (like a date picker or a select list).
    """
    type = StringProperty(required=True, choices=['date', 'choice_list'])
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

    @property
    def choices(self):
        return []


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


class MultibarAggregateChartSpec(ChartSpec):
    type = TypeProperty('multibar-aggregate')
    primary_aggregation = StringProperty(required=True)
    secondary_aggregation = StringProperty(required=True)
    value_column = StringProperty(required=True)
