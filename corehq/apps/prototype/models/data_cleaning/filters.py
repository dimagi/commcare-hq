from django.utils.translation import gettext_lazy


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

    def __init__(self, column_map, slug, match, value):
        self.column_map = column_map
        self.slug = slug
        self.match = match
        self.value = value

    def match_name(self):
        return dict(ColumnMatchType.OPTIONS)[self.match]

    def column_name(self):
        return self.column_map[self.slug].verbose_name

    def apply_filter(self, table_data):
        match_function = dict(ColumnMatchType.MATCH_FUNCTION)[self.match]
        return [data for data in table_data
                if match_function(data.get(self.slug), self.value)]
