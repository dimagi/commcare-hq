# coding=utf-8
from sqlagg.columns import SimpleColumn
import sqlalchemy
import sqlagg

from corehq.apps.reports.basic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesHeader, \
    DataTablesColumn, DTSortType
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings
from corehq.apps.reports.util import format_datatables_data


class SqlReportException(Exception):
    pass


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
    def __init__(self, header, agg_column, format_fn=None, *args, **kwargs):
        """
        Args:
            :param header:
                The column header.
            :param name:
                The name of the column. This must match up to a column name in the report database.
            :param args:
                Additional positional arguments will be passed on when creating the DataTablesColumn
            :param agg_column:
                Instance of sqlagg column class. See sqlagg.columns.BaseColumn
        Kwargs:
            :param header_group=None:
                An instance of corehq.apps.reports.datatables.DataTablesColumnGroup to which this column header will
                be added.
            :param sortable:
                Indicates if the column should be sortable. If true and no format_fn is provided then
                the default datatables format function is used. Defaults to True.
            :param sort_type:
                See corehq.apps.reports.datatables.DTSortType
            :param format_fn=None:
                Function to apply to value before display. Useful for formatting and sorting.
                See corehq.apps.reports.util.format_datatables_data
            :param kwargs:
                Additional keyword arguments will be passed on when creating the DataTablesColumn

        """
        if 'sortable' not in kwargs:
            kwargs['sortable'] = True

        if kwargs['sortable'] and 'sort_type' not in kwargs and not isinstance(agg_column, SimpleColumn):
            kwargs['sort_type'] = DTSortType.NUMERIC
            format_fn = format_fn or format_data

        self.view = agg_column

        self.header_group = kwargs.pop('header_group', None)
        self.header = header

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
            :param sortable:
                Indicates if the column should be sortable. If true and no format_fn is provided then
                the default datatables format function is used. Defaults to True.
            :param sort_type:
                See corehq.apps.reports.datatables.DTSortType
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


class SqlData(object):
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
    @memoized
    def keys(self):
        """
        The list of report keys (e.g. users) or None to just display all the data returned from the query. Each value
        in this list should be a list of the same dimension as the 'group_by' list. If group_by is None then keys
        must also be None.

        e.g.
            group_by = ['region', 'sub_region']
            keys = [['region1', 'sub1'], ['region1', 'sub2'] ... ]
        """
        return None

    @property
    def query_context(self):
        return sqlagg.QueryContext(self.table_name, self.filters, self.group_by)

    @property
    def data(self):
        if self.keys is not None and not self.group_by:
            raise SqlReportException('Keys supplied without group_by.')

        qc = self.query_context
        for c in self.columns:
            qc.append_column(c.view)
        engine = sqlalchemy.create_engine(settings.SQL_REPORTING_DATABASE_URL)
        conn = engine.connect()
        try:
            data = qc.resolve(conn, self.filter_values)
        finally:
            conn.close()

        return data


class SqlTabularReport(SqlData, GenericTabularReport):
    no_value = '--'
    exportable = True

    @property
    def fields(self):
        return [cls.__module__ + '.' + cls.__name__
                for cls in self.field_classes]

    @property
    def headers(self):
        return DataTablesHeader(*[c.data_tables_column for c in self.columns])

    @property
    def rows(self):
        return TableDataFormatter.from_sqldata(self, no_value=self.no_value).format()


class BaseDataFormatter(object):

    @classmethod
    def from_sqldata(cls, sqldata, no_value='--', row_filter=None):
        return cls(sqldata.data, sqldata.columns,
                   keys=sqldata.keys, group_by=sqldata.group_by,
                   no_value=no_value, row_filter=row_filter)

    def __init__(self, data, columns, keys=None, group_by=None, no_value='--', row_filter=None):
        self.data = data
        self.columns = columns
        self.keys = keys
        self.group_by = group_by
        self.no_value = no_value
        self.row_filter = row_filter

    def format(self):
        """
        Return tuple of row key and formatted row
        """
        if self.keys is not None and self.group_by:
            for key_group in self.keys:
                row_key = self._row_key(key_group)
                row = self.data.get(row_key, None)
                if not row:
                    row = dict(zip(self.group_by, key_group))

                yield row_key, self.format_row(row)
        elif self.group_by:
            for key, row in self.data.items():
                yield key, self.format_row(row)
        else:
            yield None, self.format_row(self.data)

    def _row_key(self, key_group):
        if len(self.group_by) == 1:
            return key_group[0]
        elif len(self.group_by) > 1:
            return tuple(key_group)

    def _or_no_value(self, value):
        return value if value is not None else self.no_value

    def format_row(self, row):
        """
        Override to implement specific row formatting
        """
        raise NotImplementedError()


class TableDataFormatter(BaseDataFormatter):
    def format_row(self, row):
        return [self._or_no_value(c.get_value(row)) for c in self.columns]

    def format(self):
        for key, row in super(TableDataFormatter, self).format():
            yield row


class DictDataFormatter(BaseDataFormatter):
    def format_row(self, row):
        return dict([(c.view.name, self._or_no_value(c.get_value(row))) for c in self.columns])

    def format(self):
        ret = dict()
        for key, row in super(DictDataFormatter, self).format():
            if key is None:
                return row
            else:
                ret[key] = row

        return ret


class SummingSqlTabularReport(SqlTabularReport):
    @property
    def rows(self):
        ret = list(super(SummingSqlTabularReport, self).rows)
        self.total_row = calculate_total_row(ret)
        return ret


def calculate_total_row(rows):
    total_row = []
    if len(rows) > 0:
        num_cols = len(rows[0])
        for i in range(num_cols):
            colrows = [cr[i] for cr in rows if isinstance(cr[i], dict)]
            colnums = [r.get('sort_key') for r in colrows if isinstance(r.get('sort_key'), (int, long))]
            total_row.append(reduce(lambda x, y: x + y, colnums, 0))

    return total_row
