import pytest
from testil import eq
from django.test import TestCase

from corehq.apps.data_cleaning.models import (
    BulkEditColumnFilter,
    DataType,
    FilterMatchType,
)
from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
)
from corehq.apps.hqwebapp.tests.tables.generator import get_case_blocks
from corehq.form_processor.tests.utils import FormProcessorTestUtils


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


@es_test(requires=[case_search_adapter], setup_class=True)
class BulkEditColumnFilterQueryTests(TestCase):
    domain = 'column-test-filters'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        case_search_es_setup(cls.domain, get_case_blocks())

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDownClass()

    def test_filter_query_is_empty(self):
        query = CaseSearchES().domain(self.domain)
        for data_type, _ in DataType.CHOICES:
            column_filter = BulkEditColumnFilter(
                prop_id='soil_contents',
                data_type=data_type,
                match_type=FilterMatchType.IS_EMPTY,
            )
            filtered_query = column_filter.filter_query(query)
            expected_query = query.empty('soil_contents')
            self.assertEqual(
                filtered_query.es_query, expected_query.es_query,
                msg=f"{data_type} failed to filter the query "
                    f"properly for FilterMatchType.is_empty"
            )

    def test_filter_query_is_not_empty(self):
        query = CaseSearchES().domain(self.domain)
        for data_type, _ in DataType.CHOICES:
            column_filter = BulkEditColumnFilter(
                prop_id='soil_contents',
                data_type=data_type,
                match_type=FilterMatchType.IS_NOT_EMPTY,
            )
            filtered_query = column_filter.filter_query(query)
            expected_query = query.non_null('soil_contents')
            self.assertEqual(
                filtered_query.es_query, expected_query.es_query,
                msg=f"{data_type} failed to filter the query "
                    f"properly for FilterMatchType.is_empty"
            )

    def test_filter_query_is_missing(self):
        query = CaseSearchES().domain(self.domain)
        for data_type, _ in DataType.CHOICES:
            column_filter = BulkEditColumnFilter(
                prop_id='soil_contents',
                data_type=data_type,
                match_type=FilterMatchType.IS_MISSING,
            )
            filtered_query = column_filter.filter_query(query)
            expected_query = query.missing('soil_contents')
            self.assertEqual(
                filtered_query.es_query, expected_query.es_query,
                msg=f"{data_type} failed to filter the query "
                    f"properly for FilterMatchType.is_empty"
            )

    def test_filter_query_is_not_missing(self):
        query = CaseSearchES().domain(self.domain)
        for data_type, _ in DataType.CHOICES:
            column_filter = BulkEditColumnFilter(
                prop_id='soil_contents',
                data_type=data_type,
                match_type=FilterMatchType.IS_NOT_MISSING,
            )
            filtered_query = column_filter.filter_query(query)
            expected_query = query.exists('soil_contents')
            self.assertEqual(
                filtered_query.es_query, expected_query.es_query,
                msg=f"{data_type} failed to filter the query "
                    f"properly for FilterMatchType.is_empty"
            )

    def filter_query_remains_unchanged_for_other_match_types(self):
        query = CaseSearchES().domain(self.domain)
        for match_type, _ in FilterMatchType.ALL_CHOICES:
            if match_type in dict(FilterMatchType.ALL_DATA_TYPES_CHOICES):
                continue
            for data_type, _ in DataType.CHOICES:
                column_filter = BulkEditColumnFilter(
                    prop_id='soil_contents',
                    data_type=data_type,
                    match_type=match_type,
                )
                filtered_query = column_filter.filter_query(query)
                self.assertEqual(
                    filtered_query.es_query, query.es_query,
                    msg=f"filtered query should remain unchanged for {data_type}, {match_type}"
                )
