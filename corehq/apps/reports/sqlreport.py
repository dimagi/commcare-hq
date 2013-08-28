# coding=utf-8
from django.template.defaultfilters import slugify
from sqlagg.columns import SimpleColumn
from sqlagg.filters import RawFilter, SqlFilter
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
    def __init__(self, header, agg_column, format_fn=None, slug=None, *args, **kwargs):
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
            :param slug=None:
                Unique ID for the column. If not supplied assumed to be 'agg_column.name'.
                This is used by the Report API.
            :param kwargs:
                Additional keyword arguments will be passed on when creating the DataTablesColumn

        """
        self.slug = slug or agg_column.name

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
    def __init__(self, header, aggregate_fn, columns, format_fn=None, slug=None, **kwargs):
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
            :param slug=None:
                Unique ID for the column. If not supplied assumed to be slugify(header).
                This is used by the Report API.
            :param sortable:
                Indicates if the column should be sortable. If true and no format_fn is provided then
                the default datatables format function is used. Defaults to True.
            :param sort_type:
                See corehq.apps.reports.datatables.DTSortType
        """
        self.aggregate_fn = aggregate_fn
        self.slug = slug or slugify(header)

        if 'sortable' not in kwargs:
            kwargs['sortable'] = True

        if kwargs['sortable'] and 'sort_type' not in kwargs:
            kwargs['sort_type'] = DTSortType.NUMERIC
            format_fn = format_fn or format_data

        self.header = header
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
        Returns a list of filter statements e.g. [EQ('date', 'enddate')]
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
    def wrapped_filters(self):
        def _wrap_if_necessary(string_or_filter):
            if isinstance(string_or_filter, basestring):
                filter = RawFilter(string_or_filter)
            else:
                filter = string_or_filter
            assert isinstance(filter, SqlFilter)
            return filter

        if self.filters:
            return [_wrap_if_necessary(f) for f in self.filters]
        else:
            return []

    @property
    def query_context(self):
        return sqlagg.QueryContext(self.table_name, self.wrapped_filters, self.group_by)

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
        formatter = DataFormatter(TableDataFormat(self.columns, no_value=self.no_value))
        return formatter.format(self.data, keys=self.keys, group_by=self.group_by)


class DataFormatter(object):

    def __init__(self, format, row_filter=None):
        self.row_filter = row_filter
        self._format = format

    def format(self, data, keys=None, group_by=None):
        row_generator = self.format_rows(data, keys=keys, group_by=group_by)
        return self._format.format_output(row_generator)

    def format_rows(self, data, keys=None, group_by=None):
        """
        Return tuple of row key and formatted row
        """
        if keys is not None and group_by:
            for key_group in keys:
                row_key = self._row_key(group_by, key_group)
                row = data.get(row_key, None)
                if not row:
                    row = dict(zip(group_by, key_group))

                formatted_row = self._format.format_row(row)
                if self.filter_row(row_key, formatted_row):
                    yield row_key, formatted_row
        elif group_by:
            for key, row in data.items():
                formatted_row = self._format.format_row(row)
                if self.filter_row(key, formatted_row):
                    yield key, formatted_row
        else:
            formatted_row = self._format.format_row(data)
            if self.filter_row(None, formatted_row):
                yield None, formatted_row

    def filter_row(self, key, row):
        return not self.row_filter or self.row_filter(key, row)

    def _row_key(self, group_by, key_group):
        if len(group_by) == 1:
            return key_group[0]
        elif len(group_by) > 1:
            return tuple(key_group)


class BaseDataFormat(object):
    def __init__(self, columns, no_value='--'):
        self.columns = columns
        self.no_value = no_value

    def format_row(self, row):
        raise NotImplementedError()

    def format_output(self, row_generator):
        raise NotImplementedError()

    def _or_no_value(self, value):
        return value if value is not None else self.no_value


class TableDataFormat(BaseDataFormat):
    def format_row(self, row):
        return [self._or_no_value(c.get_value(row)) for c in self.columns]

    def format_output(self, row_generator):
        for key, row in row_generator:
            yield row


class DictDataFormat(BaseDataFormat):
    """
    Formats the report data as a dictionary
    """
    def format_row(self, row):
        return dict([(c.slug, self._or_no_value(c.get_value(row))) for c in self.columns])

    def format_output(self, row_generator):
        ret = dict()
        for key, row in row_generator:
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
