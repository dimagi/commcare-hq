from collections import namedtuple
import json

from datetime import date
from django.utils.translation import ugettext as _
from jsonobject.exceptions import BadValueError
from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.userreports.exceptions import InvalidQueryColumn
from corehq.apps.userreports.expressions import ExpressionFactory

from corehq.apps.userreports.reports.sorting import ASCENDING, DESCENDING
from corehq.apps.userreports.const import DEFAULT_MAXIMUM_EXPANSION
from couchforms.jsonobject_extensions import GeoPointProperty
from dimagi.ext.jsonobject import (
    BooleanProperty,
    DictProperty,
    IntegerProperty,
    JsonObject,
    ListProperty,
    ObjectProperty,
    StringProperty,
)
from jsonobject.base import DefaultProperty
from sqlagg import CountUniqueColumn, SumColumn, CountColumn, MinColumn, MaxColumn, MeanColumn
from sqlagg.columns import (
    MonthColumn,
    SimpleColumn,
    YearColumn,
)
from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn
from corehq.apps.userreports.columns import ColumnConfig, get_expanded_column_config
from corehq.apps.userreports.specs import TypeProperty
from corehq.apps.userreports.transforms.factory import TransformFactory
from corehq.apps.userreports.util import localize
from corehq.apps.es import aggregations
from dimagi.utils.decorators.memoized import memoized


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

ES_AGG_MAP = {
    'avg': aggregations.AvgAggregation,
    'count': aggregations.ValueCountAggregation,
    'count_unique': aggregations.CardinalityAggregation,
    'min': aggregations.MinAggregation,
    'max': aggregations.MaxAggregation,
    'sum': aggregations.SumAggregation,
    'simple': lambda x, y: None,  # this is not an aggregation
    # these can be implemented, but will need some python level interpretation
    # should use date aggregation with a format and merge equal key_as_string
    # 'month': MonthColumn,
    # 'year': YearColumn,
}


class BaseReportColumn(JsonObject):
    type = StringProperty(required=True)
    column_id = StringProperty(required=True)
    display = DefaultProperty()
    description = StringProperty()

    @classmethod
    def wrap(cls, obj):
        if 'display' not in obj and 'column_id' in obj:
            obj['display'] = obj['column_id']
        return super(BaseReportColumn, cls).wrap(obj)

    def get_header(self, lang):
        return localize(self.display, lang)

    def get_column_ids(self):
        """
        Used as an abstraction layer for columns that can contain more than one data column
        (for example, PercentageColumns).
        """
        return [self.column_id]

    def get_column_config(self, data_source_config, lang):
        raise NotImplementedError('subclasses must override this')

    def aggregations(self, data_source_config, lang):
        """
        Returns a list of aggregations to be used in an ES query
        """
        raise NotImplementedError('subclasses must override this')

    def get_es_data(self, row, data_source_config, lang, from_aggregation=True):
        """
        Returns a dictionary of the data of this column from an ES query
        """
        raise NotImplementedError('subclasses must override this')


class ReportColumn(BaseReportColumn):
    transform = DictProperty()
    calculate_total = BooleanProperty(default=False)

    def format_data(self, data):
        """
        Subclasses can apply formatting to the entire dataset.
        """
        pass

    def get_format_fn(self):
        """
        A function that gets applied to the data just in time before the report is rendered.
        """
        if self.transform:
            return TransformFactory.get_transform(self.transform).get_transform_function()
        return None

    def get_query_column_ids(self):
        """
        Gets column IDs associated with a query. These could be different from
        the normal column_ids if the same column ends up in multiple columns in
        the query (e.g. an aggregate date splitting into year and month)
        """
        raise InvalidQueryColumn(_("You can't query on columns of type {}".format(self.type)))


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
    sortable = BooleanProperty(default=False)

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

    def get_column_config(self, data_source_config, lang):
        return ColumnConfig(columns=[
            DatabaseColumn(
                header=self.get_header(lang),
                agg_column=SQLAGG_COLUMN_MAP[self.aggregation](self.field, alias=self.column_id),
                sortable=self.sortable,
                data_slug=self.column_id,
                format_fn=self.get_format_fn(),
                help_text=self.description
            )
        ])

    def aggregations(self, data_source_config, lang):
        return filter(None, [ES_AGG_MAP[self.aggregation](self.column_id, self.field)])

    def get_es_data(self, row, data_source_config, lang, from_aggregation=True):
        if not from_aggregation:
            value = row[self.field]
        elif self.aggregation == 'simple':
            value = row['past_bucket_values'][self.field]
        else:
            value = int(row[self.column_id]['value'])

        return {self.column_id: value}

    def get_query_column_ids(self):
        return [self.column_id]


class LocationColumn(ReportColumn):
    type = TypeProperty('location')
    field = StringProperty(required=True)
    sortable = BooleanProperty(default=False)

    def format_data(self, data):
        column_name = self.column_id
        for row in data:
            try:
                row[column_name] = '{g.latitude} {g.longitude} {g.altitude} {g.accuracy}'.format(
                    g=GeoPointProperty().wrap(row[column_name])
                )
            except BadValueError:
                row[column_name] = '{} ({})'.format(row[column_name], _('Invalid Location'))

    def get_column_config(self, data_source_config, lang):
        return ColumnConfig(columns=[
            DatabaseColumn(
                header=self.get_header(lang),
                agg_column=SimpleColumn(self.field, alias=self.column_id),
                sortable=self.sortable,
                data_slug=self.column_id,
                format_fn=self.get_format_fn(),
                help_text=self.description
            )
        ])


class ExpandedColumn(ReportColumn):
    type = TypeProperty('expanded')
    field = StringProperty(required=True)
    max_expansion = IntegerProperty(default=DEFAULT_MAXIMUM_EXPANSION)

    @classmethod
    def wrap(cls, obj):
        # lazy migrations for legacy data.
        # todo: remove once all reports are on new format
        _add_column_id_if_missing(obj)
        return super(ExpandedColumn, cls).wrap(obj)

    def get_column_config(self, data_source_config, lang):
        return get_expanded_column_config(data_source_config, self, lang)

    def aggregations(self, data_source_config, lang):
        return [c.aggregation for c in self.get_column_config(data_source_config, lang).columns]

    def get_es_data(self, row, data_source_config, lang, from_aggregation=True):
        sub_columns = self.get_column_config(data_source_config, lang).columns
        ret = {}

        if not from_aggregation:
            for counter, sub_col in enumerate(sub_columns):
                ui_col = self.column_id + "-" + str(counter)
                if row[self.column_id] == sub_col.expand_value:
                    ret[ui_col] = 1
                else:
                    ret[ui_col] = 0
        else:
            for sub_col in sub_columns:
                ret[sub_col.ui_alias] = sub_col.get_es_data(row)
        return ret


class AggregateDateColumn(ReportColumn):
    """
    Used for grouping months and years together.
    """
    type = TypeProperty('aggregate_date')
    field = StringProperty(required=True)
    format = StringProperty(required=False)

    def get_column_config(self, data_source_config, lang):
        return ColumnConfig(columns=[
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
        def _format(data):
            if not data.get('year', None) or not data.get('month', None):
                return _('Unknown Date')
            format_ = self.format or '%Y-%m'
            return date(year=int(data['year']), month=int(data['month']), day=1).strftime(format_)
        return _format

    def get_query_column_ids(self):
        return [self._year_column_alias(), self._month_column_alias()]


class PercentageColumn(ReportColumn):
    type = TypeProperty('percent')
    numerator = ObjectProperty(FieldColumn, required=True)
    denominator = ObjectProperty(FieldColumn, required=True)
    format = StringProperty(
        choices=['percent', 'fraction', 'both', 'numeric_percent', 'decimal'],
        default='percent'
    )

    def get_column_config(self, data_source_config, lang):
        # todo: better checks that fields are not expand
        num_config = self.numerator.get_column_config(data_source_config, lang)
        denom_config = self.denominator.get_column_config(data_source_config, lang)
        return ColumnConfig(columns=[
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


class CalculatedColumn(namedtuple('CalculatedColumn', ['header', 'slug'])):

    @property
    def data_tables_column(self):
        return DataTablesColumn(self.header, sortable=False, data_slug=self.slug)


class ExpressionColumn(BaseReportColumn):
    expression = DefaultProperty(required=True)

    @property
    def calculate_total(self):
        """Calculating total not supported"""
        # Using a function property so that it can't be overridden during wrapping
        return False

    @property
    @memoized
    def wrapped_expression(self):
        return ExpressionFactory.from_spec(self.expression)

    def get_column_config(self, data_source_config, lang):
        return ColumnConfig(columns=[
            CalculatedColumn(
                header=self.get_header(lang),
                slug=self.column_id,
                # todo: are these needed?
                # format_fn=self.get_format_fn(),
                # help_text=self.description
            )
        ])


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


class GraphDisplayColumn(JsonObject):
    column_id = StringProperty(required=True)
    display = StringProperty(required=True)

    @classmethod
    def wrap(cls, obj):
        # automap column_id to display if display isn't set
        if isinstance(obj, dict) and 'column_id' in obj and 'display' not in obj:
            obj['display'] = obj['column_id']
        return super(GraphDisplayColumn, cls).wrap(obj)


class MultibarChartSpec(ChartSpec):
    type = TypeProperty('multibar')
    aggregation_column = StringProperty()
    x_axis_column = StringProperty(required=True)
    y_axis_columns = ListProperty(GraphDisplayColumn)
    is_stacked = BooleanProperty(default=False)

    @classmethod
    def wrap(cls, obj):
        def _convert_columns_to_properly_dicts(cols):
            for column in cols:
                if isinstance(column, basestring):
                    yield {'column_id': column, 'display': column}
                else:
                    yield column
        obj['y_axis_columns'] = list(_convert_columns_to_properly_dicts(obj.get('y_axis_columns', [])))
        return super(MultibarChartSpec, cls).wrap(obj)


class MultibarAggregateChartSpec(ChartSpec):
    type = TypeProperty('multibar-aggregate')
    primary_aggregation = StringProperty(required=True)
    secondary_aggregation = StringProperty(required=True)
    value_column = StringProperty(required=True)


class OrderBySpec(JsonObject):
    field = StringProperty()
    order = StringProperty(choices=[ASCENDING, DESCENDING], default=ASCENDING)
