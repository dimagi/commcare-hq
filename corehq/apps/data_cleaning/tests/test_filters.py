import pytest
from testil import eq

from corehq.apps.data_cleaning.models import (
    BulkEditColumnFilter,
    DataType,
    FilterMatchType,
)


@pytest.mark.parametrize("category, valid_match_types", [
    (DataType.FILTER_CATEGORY_TEXT, (
        FilterMatchType.EXACT,
        FilterMatchType.IS_NOT,
        FilterMatchType.STARTS,
        FilterMatchType.STARTS_NOT,
        FilterMatchType.FUZZY,
        FilterMatchType.FUZZY_NOT,
        FilterMatchType.PHONETIC,
        FilterMatchType.PHONETIC_NOT,
        FilterMatchType.IS_EMPTY,
        FilterMatchType.IS_NOT_EMPTY,
        FilterMatchType.IS_MISSING,
        FilterMatchType.IS_NOT_MISSING,
    )),
    (DataType.FILTER_CATEGORY_NUMBER, (
        FilterMatchType.EXACT,
        FilterMatchType.IS_NOT,
        FilterMatchType.LESS_THAN,
        FilterMatchType.LESS_THAN_EQUAL,
        FilterMatchType.GREATER_THAN,
        FilterMatchType.GREATER_THAN_EQUAL,
        FilterMatchType.IS_EMPTY,
        FilterMatchType.IS_NOT_EMPTY,
        FilterMatchType.IS_MISSING,
        FilterMatchType.IS_NOT_MISSING,
    )),
    (DataType.FILTER_CATEGORY_DATE, (
        FilterMatchType.EXACT,
        FilterMatchType.LESS_THAN,
        FilterMatchType.LESS_THAN_EQUAL,
        FilterMatchType.GREATER_THAN,
        FilterMatchType.GREATER_THAN_EQUAL,
        FilterMatchType.IS_EMPTY,
        FilterMatchType.IS_NOT_EMPTY,
        FilterMatchType.IS_MISSING,
        FilterMatchType.IS_NOT_MISSING,
    )),
    (DataType.FILTER_CATEGORY_MULTI_SELECT, (
        FilterMatchType.IS_ANY,
        FilterMatchType.IS_NOT_ANY,
        FilterMatchType.IS_ALL,
        FilterMatchType.IS_NOT_ALL,
        FilterMatchType.IS_EMPTY,
        FilterMatchType.IS_NOT_EMPTY,
        FilterMatchType.IS_MISSING,
        FilterMatchType.IS_NOT_MISSING,
    )),
])
def test_data_and_match_type_validation(category, valid_match_types):
    for data_type in DataType.FILTER_CATEGORY_DATA_TYPES[category]:
        for match_type, _ in FilterMatchType.ALL_CHOICES:
            is_valid = BulkEditColumnFilter.is_data_and_match_type_valid(
                match_type, data_type
            )
            if match_type in valid_match_types:
                eq(is_valid, True,
                   text=f"FilterMatchType {match_type} should support DataType {data_type}")
            else:
                eq(is_valid, False,
                   text=f"FilterMatchType {match_type} should NOT support DataType {data_type}")
