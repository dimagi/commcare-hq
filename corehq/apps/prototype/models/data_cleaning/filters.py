from django.utils.translation import gettext_lazy

from corehq.apps.prototype.models.data_cleaning.cache_store import FilterColumnStore
from corehq.apps.prototype.models.data_cleaning.tables import FakeCaseTable


class ColumnMatchType:
    EXACT = "exact"
    CONTAINS = "contains"
    STARTS = "starts"
    ENDS = "ends"

    OPTIONS = (
        (EXACT, gettext_lazy("Exact")),
        (CONTAINS, gettext_lazy("Contains")),
        (STARTS, gettext_lazy("Starts with")),
        (ENDS, gettext_lazy("Ends with")),
    )

    MATCH_FUNCTION = (
        (EXACT, lambda data, value: data == value),
        (CONTAINS, lambda data, value: value in data),
        (STARTS, lambda data, value: data.startswith(value)),
        (ENDS, lambda data, value: data.endswith(value)),
    )


class ColumnFilter:
    """Not intended for production use!
    Use this only for in-memory prototype!"""
    table_config = FakeCaseTable

    def __init__(self, slug, match, value):
        self.slug = slug
        self.match = match
        self.value = value

    def match_name(self):
        return dict(ColumnMatchType.OPTIONS)[self.match]

    def column_name(self):
        return dict(FakeCaseTable.available_columns)[self.slug].verbose_name

    @classmethod
    def get_filters_from_cache(cls, request):
        return [
            cls(*args)
            for args in FilterColumnStore(request).get()
        ]

    @classmethod
    def add_filter(cls, request, slug, match, value):
        filter_store = FilterColumnStore(request)
        filters = filter_store.get()
        filters.append([slug, match, value])
        filter_store.set(filters)

    @classmethod
    def delete_filter(cls, request, index):
        filter_store = FilterColumnStore(request)
        filters = filter_store.get()
        try:
            del filters[index]
        except IndexError:
            pass
        filter_store.set(filters)

    @classmethod
    def filter_table_from_cache(cls, request, table_data):
        for column_filter in cls.get_filters_from_cache(request):
            table_data = column_filter.get_filtered_table_data(table_data)
        return table_data

    def get_filtered_table_data(self, table_data):
        match_function = dict(ColumnMatchType.MATCH_FUNCTION)[self.match]
        return [data for data in table_data
                if match_function(data.get(self.slug), self.value)]
