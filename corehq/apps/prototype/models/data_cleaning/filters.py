import re

from django.utils.translation import gettext_lazy


def _is_less_than(data, value):
    if data is None:
        return False
    if not isinstance(data, int):
        return data < value
    try:
        return data < int(value)
    except ValueError:
        return str(data) < value


def _is_greater_than(data, value):
    if data is None:
        return False
    if not isinstance(data, int):
        return data > value
    try:
        return data > int(value)
    except ValueError:
        return str(data) > value


class ColumnMatchType:
    EXACT = "exact"
    IS_NOT = "is_not"
    CONTAINS = "contains"
    CONTAINS_NOT = "contains_not"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    LESS_THAN = "lt"
    GREATER_THAN = "gt"
    STARTS = "starts"
    ENDS = "ends"

    OPTIONS = (
        (EXACT, gettext_lazy("is exactly")),
        (IS_NOT, gettext_lazy("is not")),
        (CONTAINS, gettext_lazy("contains")),
        (CONTAINS_NOT, gettext_lazy("does not contain")),
        (IS_EMPTY, gettext_lazy("is empty")),
        (IS_NOT_EMPTY, gettext_lazy("is not empty")),
        (IS_NULL, gettext_lazy("is null")),
        (IS_NOT_NULL, gettext_lazy("is not null")),
        (LESS_THAN, gettext_lazy("is less than")),
        (GREATER_THAN, gettext_lazy("is greater than")),
        (STARTS, gettext_lazy("starts with")),
        (ENDS, gettext_lazy("ends with")),
    )

    MATCH_FUNCTION = (
        (EXACT, lambda data, value: data is not None and str(data) == value),
        (IS_NOT, lambda data, value: data is not None and str(data) != value),
        (CONTAINS, lambda data, value: data is not None and value.lower() in str(data).lower()),
        (CONTAINS_NOT, lambda data, value: data is not None and value.lower() not in str(data).lower()),
        (IS_EMPTY, lambda data, value: data is not None and str(data) == ""),
        (IS_NOT_EMPTY, lambda data, value: data is not None and str(data) != ""),
        (IS_NULL, lambda data, value: data is None),
        (IS_NOT_NULL, lambda data, value: data is not None),
        (LESS_THAN, _is_less_than),
        (GREATER_THAN, _is_greater_than),
        (STARTS, lambda data, value: data is not None and str(data).startswith(value)),
        (ENDS, lambda data, value: data is not None and str(data).endswith(value)),
    )

    REGEX_MATCH_FUNCTION = (
        (EXACT, lambda data, value: data is not None and re.match(re.compile(f"^{value}$"), str(data))),
        (IS_NOT, lambda data, value: data is not None and not re.match(re.compile(f"^{value}$"), str(data))),
        (CONTAINS, lambda data, value: data is not None and re.search(re.compile(value), str(data))),
        (CONTAINS_NOT, lambda data, value: data is not None and not re.search(re.compile(value), str(data))),
    )

    NO_VALUE_MATCHES = (
        IS_EMPTY, IS_NULL, IS_NOT_EMPTY, IS_NOT_NULL
    )

    NEGATIVE_STRING_MATCHES = (
        IS_NOT, CONTAINS_NOT,
    )

    REGEX_MATCHES = (
        EXACT, IS_NOT, CONTAINS, CONTAINS_NOT,
    )


class ColumnFilter:
    """Not intended for production use!
    Use this only for in-memory prototype!"""

    def __init__(self, column_map, slug, match, value, use_regex):
        self.column_map = column_map
        self.slug = slug
        self.match = match
        self.value = value
        self.use_regex = use_regex

    def match_name(self):
        return dict(ColumnMatchType.OPTIONS)[self.match]

    def column_name(self):
        return self.column_map[self.slug].verbose_name

    def apply_filter(self, table_data):
        match_function = dict(ColumnMatchType.MATCH_FUNCTION)[self.match]
        if self.use_regex:
            match_function = dict(ColumnMatchType.REGEX_MATCH_FUNCTION).get(
                self.match, match_function
            )
        return [data for data in table_data
                if match_function(data.get(self.slug), self.value)]
