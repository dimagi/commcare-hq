# coding=utf-8
from sqlagg.columns import SimpleColumn
import sqlalchemy
import sqlagg

from corehq.apps.reports.basic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesHeader, \
    DataTablesColumn, DTSortType
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings
from corehq.apps.reports.util import format_datatables_data


def format_data(value):
        if value is not None:
            return format_datatables_data(value, value)
        else:
            return value


class Column(object):
    """
    Base object for Column classes.
    """
    format_for_sorting = False

    def __init__(self, format_fn=None):
        self.format_fn = format_fn

    def get_value(self, row):
        value = self.get_raw_value(row)
        if value is not None and self.format_fn:
            return self.format_fn(value)
        else:
            return value

    def get_raw_value(self, row):
        """
        Given a row of report data represented as a dict this method should return the raw value for
        this column or None.
        """
        raise NotImplementedError()


class DatabaseColumn(Column):
    def __init__(self, header, name, column_type=sqlagg.SumColumn, format_fn=None, *args, **kwargs):
        """
        Args:
            :param header:
                The column header.
            :param name:
                The name of the column. This must match up to a column name in the report database.
            :param args:
                Additional positional arguments will be passed on when creating the DataTablesColumn
        Kwargs:
            :param column_type=SumColumn:
                The type of the column. Must be a subclass of sqlagg.columns.BaseColumn.
            :param header_group=None:
                An instance of corehq.apps.reports.datatables.DataTablesColumnGroup to which this column header will
                be added.
            :param format_fn=None:
                Function to apply to value before display. Useful for formatting and sorting.
                See corehq.apps.reports.util.format_datatables_data
            :param alias=None:
                The alias to use for the column (optional). Should only contain a-z, A-Z, 0-9 and '_' characters.
                This is useful if you want to select data from the same table column more than once in a single report.
                e.g
                    Column("Count", "col_a", column_type=CountColumn, alias="count_col_a")
                    Column("Sum", "col_a", column_type=SumColumn, alias="sum_col_a")
            :param table_name=None:
                This will override the table name supplied to the QueryContext. See QueryContext.
            :param group_by=None:
                This will override the group_by values supplied to the QueryContext. See QueryContext.
            :param filters=None:
                This will override the filters supplied to the QueryContext. See QueryContext.
            :param kwargs:
                Additional keyword arguments will be passed on when creating the DataTablesColumn

        """
        column_args = (
            # args specific to BaseColumn constructor
            'table_name', 'group_by', 'filters', 'alias'
        )
        column_kwargs = {}

        for arg in column_args:
            try:
                column_kwargs[arg] = kwargs.pop(arg)
            except KeyError:
                pass

        if 'sortable' not in kwargs:
            kwargs['sortable'] = True

        if kwargs['sortable'] and 'sort_type' not in kwargs and not isinstance(column_type, SimpleColumn):
            kwargs['sort_type'] = DTSortType.NUMERIC
            format_fn = format_fn or format_data

        self.view = column_type(name, **column_kwargs)

        self.header_group = kwargs.pop('header_group', None)

        self.data_tables_column = DataTablesColumn(header, *args, **kwargs)
        if self.header_group:
            self.header_group.add_column(self.data_tables_column)

        super(DatabaseColumn, self).__init__(format_fn=format_fn)

    def get_raw_value(self, row):
        return self.view.get_value(row) if row else None


class AggregateColumn(Column):
    """
    Allows combining the values from multiple columns into a single value.
    """
    def __init__(self, header, aggregate_fn, *columns, **kwargs):
        """
        Args:
            :param header:
                The column header.
            :param aggregate_fn:
                The function used to aggregate the individual values into a single value.
            :param columns:
                List of columns (instances of sqlagg.BaseColumn).
        Kwargs:
            :param format_fn=None:
                Function to apply to value before display. Useful for formatting and sorting.
                See corehq.apps.reports.util.format_datatables_data
        """
        self.aggregate_fn = aggregate_fn
        format_fn = kwargs.pop('format_fn', None)

        if 'sortable' not in kwargs:
            kwargs['sortable'] = True

        if kwargs['sortable'] and 'sort_type' not in kwargs:
            kwargs['sort_type'] = DTSortType.NUMERIC
            format_fn = format_fn or format_data

        self.header_group = kwargs.pop('header_group', None)
        self.data_tables_column = DataTablesColumn(header, **kwargs)
        if self.header_group:
            self.header_group.add_column(self.data_tables_column)

        self.view = sqlagg.AggregateColumn(aggregate_fn, *columns)

        super(AggregateColumn, self).__init__(format_fn=format_fn)

    def get_raw_value(self, row):
        return self.view.get_value(row) if row else None


class SqlTabularReport(GenericTabularReport):
    exportable = True
    no_value = '--'
    table_name = None

    @property
    def columns(self):
        """
        Returns a list of Column objects
        """
        raise NotImplementedError()

    @property
    def group_by(self):
        """
        Returns a list of 'group by' column names
        """
        raise NotImplementedError()

    @property
    def filters(self):
        """
        Returns a list of filter statements e.g. ["date > :enddate"]
        """
        raise NotImplementedError()

    @property
    def filter_values(self):
        """
        Return a dict mapping the filter keys to actual values e.g. {"enddate": date(2013,01,01)}
        """
        raise NotImplementedError()

    @property
    def keys(self):
        """
        The list of report keys (e.g. users) or None to just display all the data returned from the query. Each value
        in this list should be a list of the same dimension as the 'group_by' list.

        e.g.
            group_by = ['region', 'sub_region']
            keys = [['region1', 'sub1'], ['region1', 'sub2'] ... ]
        """
        return None

    @property
    def fields(self):
        return [cls.__module__ + '.' + cls.__name__
                for cls in self.field_classes]

    @property
    def headers(self):
        return DataTablesHeader(*[c.data_tables_column for c in self.columns])

    @property
    def query_context(self):
        return sqlagg.QueryContext(self.table_name, self.filters, self.group_by)

    @property
    def rows(self):
        qc = self.query_context
        for c in self.columns:
            qc.append_column(c.view)
        engine = sqlalchemy.create_engine(settings.SQL_REPORTING_DATABASE_URL)
        conn = engine.connect()
        try:
            data = qc.resolve(conn, self.filter_values)
        finally:
            conn.close()

        if self.keys:
            for key_group in self.keys:
                row_key = self._row_key(key_group)
                row = data.get(row_key, None) if row_key else data
                if not row:
                    row = dict(zip(self.group_by, key_group))
                yield [self._or_no_value(c.get_value(row)) for c in self.columns]
        else:
            if self.group_by:
                for k, v in data.items():
                    yield [self._or_no_value(c.get_value(data.get(k))) for c in self.columns]
            else:
                yield [self._or_no_value(c.get_value(data)) for c in self.columns]

    def _row_key(self, key_group):
        if len(self.group_by) == 1:
            return key_group[0]
        elif len(self.group_by) > 1:
            return tuple(key_group)

    def _or_no_value(self, value):
        return value if value is not None else self.no_value


class SummingSqlTabularReport(SqlTabularReport):
    @property
    def rows(self):
        ret = list(super(SummingSqlTabularReport, self).rows)
        if len(ret) > 0:
            num_cols = len(ret[0])
            total_row = []
            for i in range(num_cols):
                colrows = [cr[i] for cr in ret if isinstance(cr[i], dict)]
                colnums = [r.get('sort_key') for r in colrows if isinstance(r.get('sort_key'), (int, long))]
                total_row.append(reduce(lambda x, y: x + y, colnums, 0))
            self.total_row = total_row
        return ret
