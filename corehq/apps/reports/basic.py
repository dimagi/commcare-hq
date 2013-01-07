from corehq.apps.reports.datatables import (DataTablesHeader, DataTablesColumn,
    DTSortType)
from corehq.apps.reports.generic import GenericTabularReport
from couchdbkit_aggregate import KeyView, AggregateView
from dimagi.utils.couch.database import get_db

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
            'key', 'couch_view', 'startkey_fn', 'endkey_fn', 'reduce_fn',

            # pass-through db.view() args
        )
        couch_kwargs = {}

        for arg in couch_args:
            try:
                couch_kwargs[arg] = kwargs.pop(arg)
            except KeyError:
                pass

        if 'key' in couch_kwargs:
            if 'sort_type' not in kwargs:
                kwargs['sort_type'] = DTSortType.NUMERIC
                kwargs['sortable'] = True

            key = couch_kwargs.pop('key')
            self.view = KeyView(key, **couch_kwargs)
        elif calculate_fn:
            kwargs['sortable'] = False
            self.view = FunctionView(calculate_fn)
        else:
            raise Exception("Must specify either key or calculate_fn.")

        self.data_tables_column = DataTablesColumn(name, *args, **kwargs)


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
        for attr_name, attr in attrs.items():
            if isinstance(attr, Column):
                columns[attr_name] = attr

        class MyAggregateView(AggregateView):
            pass

        # patch MyAggregateView's key_views attribute since we can't define the
        # class declaratively
        function_views = {}
        for slug, column in columns.items():
            if hasattr(column, 'view') and isinstance(column.view, KeyView):
                MyAggregateView.key_views[slug] = column.view
            else:
                function_views[slug] = column.view

        attrs['columns'] = columns
        attrs['function_views'] = function_views
        attrs['View'] = MyAggregateView

        return super(ColumnCollector, cls).__new__(cls, name, bases, attrs)


class BasicTabularReport(GenericTabularReport):
    __metaclass__ = ColumnCollector

    @property
    def fields(self):
        return [cls.__module__ + '.' + cls.__name__
                for cls in self.field_classes]

    @property
    def headers(self):
        return DataTablesHeader(*[self.columns[c].data_tables_column
                                  for c in self.default_column_order])

    @property
    def rows(self):
        startkey, endkey = self.start_and_end_keys
        kwargs = {
            'db': get_db(),
            'couch_view': getattr(self, 'couch_view', None),
            'startkey': startkey,
            'endkey': endkey
        }

        for key in self.keys:
            row = self.View.view(key, **kwargs)

            yield [row[c] if c in self.View.key_views
                          else self.function_views[c].view(key, self)
                   for c in self.default_column_order]
