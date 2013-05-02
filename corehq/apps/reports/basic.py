from django.conf import settings
from corehq.apps.reports.datatables import (DataTablesHeader, DataTablesColumn,
    DTSortType)
from corehq.apps.reports.generic import GenericTabularReport
from couchdbkit_aggregate import AggregateView, KeyView, AggregateKeyView
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized

__all__ = ['Column', 'BasicTabularReport']

class Column(object):
    """
    Unified interface for a report column that lets you specify the
    DataTablesColumn arguments (UI) and CouchDB KeyView arguments (model) at
    once.

    """

    def __init__(self, name, calculate_fn=None, *args, **kwargs):

        couch_args = (
            # args specific to KeyView constructor
            'key', 'couch_view', 'startkey_fn', 'endkey_fn', 'reduce_fn'

            # pass-through db.view() args
        )
        couch_kwargs = {}

        for arg in couch_args:
            try:
                couch_kwargs[arg] = kwargs.pop(arg)
            except KeyError:
                pass

        self.group = kwargs.pop('group', None)

        if 'key' in couch_kwargs:
            if 'sort_type' not in kwargs:
                kwargs['sort_type'] = DTSortType.NUMERIC
                kwargs['sortable'] = True

            key = couch_kwargs.pop('key')
            if isinstance(key, AggregateKeyView):
                self.view = key
            else:
                self.view = KeyView(key, **couch_kwargs)
        elif calculate_fn:
            kwargs['sortable'] = False
            self.view = FunctionView(calculate_fn)
        else:
            raise Exception("Must specify either key or calculate_fn.")

        self.data_tables_column = DataTablesColumn(name, *args, **kwargs)
        if self.group:
            self.group.add_column(self.data_tables_column)


class FunctionView(object):

    def __init__(self, calculate_fn):
        if isinstance(calculate_fn, type):
            calculate_fn = calculate_fn()
        self.calculate_fn = calculate_fn

    def view(self, key, object):
        return self.calculate_fn(key, object)


class ColumnCollector(type):
    """
    Metaclass that collects Columns and translates them to KeyViews of an
    AggregateView.

    """
    def __new__(cls, name, bases, attrs):
        columns = {}
        for base in bases:
            columns.update(getattr(base, 'columns', {}))
        for attr_name, attr in attrs.items():
            if isinstance(attr, Column):
                columns[attr_name] = attr

        class MyAggregateView(AggregateView):
            pass

        # patch MyAggregateView's key_views attribute since we can't define the
        # class declaratively
        function_views = {}
        for slug, column in columns.items():
            if hasattr(column, 'view') and isinstance(column.view, (KeyView, AggregateKeyView)):
                MyAggregateView.key_views[slug] = column.view
            else:
                function_views[slug] = column.view

        attrs['columns'] = columns
        attrs['function_views'] = function_views
        attrs['View'] = MyAggregateView

        return super(ColumnCollector, cls).__new__(cls, name, bases, attrs)


class BasicTabularReport(GenericTabularReport):
    __metaclass__ = ColumnCollector
    update_after = False

    @property
    def default_column_order(self):
        raise NotImplementedError()

    @property
    def keys(self):
        raise NotImplementedError()

    @property
    def start_and_end_keys(self):
        raise NotImplementedError()

    @property
    def fields(self):
        return [cls.__module__ + '.' + cls.__name__
                for cls in self.field_classes]

    @property
    def headers(self):
        columns = []
        groups = []
        for c in self.default_column_order:
            column = self.columns[c]
            if column.group and column.group not in groups:
                columns.append(column.group)
                groups.append(column.group)
            elif not column.group:
                columns.append(column.data_tables_column)

        return DataTablesHeader(*columns)

    @property
    def rows(self):
        kwargs = {'stale': settings.COUCH_STALE_QUERY} if self.update_after else {}
        startkey, endkey = self.start_and_end_keys
        kwargs.update({
            'db': get_db(),
            'couch_view': getattr(self, 'couch_view', None),
            'startkey': startkey,
            'endkey': endkey
        })

        for key in self.keys:
            row = self.View.get_result(key, **kwargs)

            yield [row[c] if c in self.View.key_views
                          else self.function_views[c].view(key, self)
                   for c in self.default_column_order]


class SummingReportMixin():
    @property
    @memoized
    def total_row(self):
        rows = list(self.rows)
        num_cols = len(rows[0])
        total_row = []
        for i in range(num_cols):
            total_row.append(reduce(lambda x, y: x+ y, [r[i] for r in rows if isinstance(r[i], (int, long))], 0))

        return total_row
