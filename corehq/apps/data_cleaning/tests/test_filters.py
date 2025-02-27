import pytest
from testil import eq
from unittest import mock

from django.test import TestCase, RequestFactory

from corehq.apps.data_cleaning.exceptions import UnsupportedFilterValueException
from corehq.apps.data_cleaning.filters import (
    CaseOwnersPinnedFilter,
    CaseStatusPinnedFilter,
)
from corehq.apps.data_cleaning.models import (
    BulkEditColumnFilter,
    DataType,
    FilterMatchType,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
)
from corehq.apps.hqwebapp.tests.tables.generator import get_case_blocks
from corehq.apps.users.models import WebUser
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


class BulkEditColumnFilterXpathTest(TestCase):

    def test_exact_text_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.EXACT,
            value='Riny Iola',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "name = 'Riny Iola'"
        )

    def test_single_quote_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.EXACT,
            value="Happy's",
        )
        self.assertEqual(
            column_filter.get_quoted_value(column_filter.value),
            '''"Happy's"'''
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            '''name = "Happy's"'''
        )

    def test_double_quote_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.EXACT,
            value='Zesty "orange" Flora',
        )
        self.assertEqual(
            column_filter.get_quoted_value(column_filter.value),
            """'Zesty "orange" Flora'"""
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            """name = 'Zesty "orange" Flora'"""
        )

    def test_mixed_quote_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.EXACT,
            value='''Zesty's "orange" Flora''',
        )
        with self.assertRaises(UnsupportedFilterValueException):
            column_filter.get_quoted_value(column_filter.value)
        with self.assertRaises(UnsupportedFilterValueException):
            column_filter.get_xpath_expression()

    def test_exact_number_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='height_cm',
            data_type=DataType.DECIMAL,
            match_type=FilterMatchType.EXACT,
            value='11.2'
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "height_cm = 11.2"
        )

    def test_exact_date_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='watered_on',
            data_type=DataType.DATE,
            match_type=FilterMatchType.EXACT,
            value='2024-12-11'
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "watered_on = '2024-12-11'"
        )

    def test_is_not_text_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='phone_num',
            data_type=DataType.PHONE_NUMBER,
            match_type=FilterMatchType.IS_NOT,
            value='11245523233',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "phone_num != '11245523233'"
        )

    def test_is_not_number_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='num_leaves',
            data_type=DataType.INTEGER,
            match_type=FilterMatchType.IS_NOT,
            value='5',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "num_leaves != 5"
        )

    def test_less_than_number_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='height_cm',
            data_type=DataType.DECIMAL,
            match_type=FilterMatchType.LESS_THAN,
            value='12.35',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "height_cm < 12.35"
        )

    def test_less_than_date_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='watered_on',
            data_type=DataType.DATETIME,
            match_type=FilterMatchType.LESS_THAN,
            value='2025-02-03 16:43',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "watered_on < '2025-02-03 16:43'"
        )

    def test_less_than_equal_number_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='weight_kg',
            data_type=DataType.DECIMAL,
            match_type=FilterMatchType.LESS_THAN_EQUAL,
            value='35.5',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "weight_kg <= 35.5"
        )

    def test_less_than_equal_date_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='last_modified',
            data_type=DataType.DATETIME,
            match_type=FilterMatchType.LESS_THAN_EQUAL,
            value='2025-02-20 16:55',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "last_modified <= '2025-02-20 16:55'"
        )

    def test_greater_than_number_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='amount',
            data_type=DataType.INTEGER,
            match_type=FilterMatchType.GREATER_THAN,
            value='15',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "amount > 15"
        )

    def test_greater_than_date_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='modified_on',
            data_type=DataType.DATE,
            match_type=FilterMatchType.GREATER_THAN,
            value='2025-01-22',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "modified_on > '2025-01-22'"
        )

    def test_greater_than_equal_number_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='num_branches',
            data_type=DataType.INTEGER,
            match_type=FilterMatchType.GREATER_THAN_EQUAL,
            value='23',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "num_branches >= 23"
        )

    def test_greater_than_equal_date_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='submitted_on',
            data_type=DataType.DATE,
            match_type=FilterMatchType.GREATER_THAN_EQUAL,
            value='2025-03-03',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "submitted_on >= '2025-03-03'"
        )

    def test_starts_with_text_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.STARTS,
            value='st',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "starts-with(name, 'st')"
        )

    def test_starts_with_text_single_quote_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.STARTS,
            value="st's",
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            """starts-with(name, "st's")"""
        )

    def test_starts_with_text_double_quote_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.STARTS,
            value='st"s',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            """starts-with(name, 'st"s')"""
        )

    def test_starts_text_mixed_quote_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.STARTS,
            value='''st"s m'd''',
        )
        with self.assertRaises(UnsupportedFilterValueException):
            column_filter.get_xpath_expression()

    def test_starts_not_text_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='favorite_park',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.STARTS_NOT,
            value='fo',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "not(starts-with(favorite_park, 'fo'))"
        )

    def test_fuzzy_text_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='pot_type',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.FUZZY,
            value='ceremic',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "fuzzy-match(pot_type, 'ceremic')"
        )

    def test_fuzzy_not_text_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='pot_type',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.FUZZY_NOT,
            value='ceremic',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "not(fuzzy-match(pot_type, 'ceremic'))"
        )

    def test_phonetic_text_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='light_level',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.PHONETIC,
            value='hi',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "phonetic-match(light_level, 'hi')"
        )

    def test_phonetic_not_text_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='light_level',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.PHONETIC_NOT,
            value='hi',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "not(phonetic-match(light_level, 'hi'))"
        )

    def test_is_any_text_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='health_issues',
            data_type=DataType.MULTIPLE_OPTION,
            match_type=FilterMatchType.IS_ANY,
            value='yellow_leaves root_rot',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "selected-any(health_issues, 'yellow_leaves root_rot')"
        )

    def test_is_not_any_text_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='health_issues',
            data_type=DataType.MULTIPLE_OPTION,
            match_type=FilterMatchType.IS_NOT_ANY,
            value='fungus root_rot',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "not(selected-any(health_issues, 'fungus root_rot'))"
        )

    def test_is_all_text_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='soil_contents',
            data_type=DataType.MULTIPLE_OPTION,
            match_type=FilterMatchType.IS_ALL,
            value='bark worm_castings',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "selected-all(soil_contents, 'bark worm_castings')"
        )

    def test_is_not_all_text_xpath(self):
        column_filter = BulkEditColumnFilter(
            prop_id='soil_contents',
            data_type=DataType.MULTIPLE_OPTION,
            match_type=FilterMatchType.IS_NOT_ALL,
            value='bark worm_castings',
        )
        self.assertEqual(
            column_filter.get_xpath_expression(),
            "not(selected-all(soil_contents, 'bark worm_castings'))"
        )

    def test_value_match_types_return_none_all_data_types_xpath(self):
        for match_type, _ in FilterMatchType.ALL_DATA_TYPES_CHOICES:
            for data_type, _ in DataType.CHOICES:
                column_filter = BulkEditColumnFilter(
                    prop_id='a_property',
                    data_type=data_type,
                    match_type=match_type,
                )
                self.assertIsNone(
                    column_filter.get_xpath_expression(),
                    msg=f"{match_type} for {data_type} should not return an xpath expression"
                )


class TestReportFilterSubclasses(TestCase):
    domain_name = 'report-filter-pinned-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain.delete)

        cls.web_user = WebUser.create(
            cls.domain.name, 'tester@datacleaning.org', 'testpwd', None, None
        )
        cls.addClassCleanup(cls.web_user.delete, cls.domain.name, deleted_by=None)

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get('/cases/')
        self.request.domain = self.domain_name
        self.request.can_access_all_locations = True
        self.request.couch_user = self.web_user
        self.request.project = self.domain

    def test_case_owners_report_filter_context(self):
        report_filter = CaseOwnersPinnedFilter(
            self.request, self.domain_name, use_bootstrap5=True
        )
        expected_context = {
            'report_select2_config': {
                'select': {
                    'options': [
                        {'val': 't__0', 'text': '[Active Mobile Workers]'}
                    ],
                    'default_text': 'Filter by...',
                    'selected': [
                        {'id': 'project_data', 'text': '[Project Data]'},
                    ],
                    'placeholder': 'Add case owners to filter this report.',
                },
                'pagination': {
                    'enabled': False,
                    'url': None,
                    'handler': '',
                    'action': None,
                },
                'endpoint': '/a/report-filter-pinned-test/reports/filters/case_list_options/',
            },
            'filter_help': [
                '<i class="fa fa-info-circle"></i> See <a href="'
                'https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/'
                '2215051298/Organization+Data+Management#Search-for-Locations" '
                'target="_blank"> Filter Definitions</a>.',
            ],
        }
        self.assertEqual(report_filter.filter_context, expected_context)

    @mock.patch.object(Domain, 'uses_locations', lambda: True)  # removes dependency on accounting
    def test_case_owners_report_filter_context_locations(self):
        report_filter = CaseOwnersPinnedFilter(
            self.request, self.domain_name, use_bootstrap5=True
        )
        expected_context = {
            'report_select2_config': {
                'select': {
                    'options': [
                        {'val': 't__0', 'text': '[Active Mobile Workers]'}
                    ],
                    'default_text': 'Filter by...',
                    'selected': [
                        {'id': 'project_data', 'text': '[Project Data]'},
                    ],
                    'placeholder': 'Add case owners to filter this report.',
                },
                'pagination': {
                    'enabled': False,
                    'url': None,
                    'handler': '',
                    'action': None,
                },
                'endpoint': '/a/report-filter-pinned-test/reports/filters/case_list_options/',
            },
            'filter_help': [
                '<i class="fa fa-info-circle"></i> See <a href="'
                'https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/'
                '2215051298/Organization+Data+Management#Search-for-Locations" '
                'target="_blank"> Filter Definitions</a>.',
                'When searching by location, put your location name in quotes to '
                'show only exact matches. To more easily find a location, you may '
                'specify multiple levels by separating with a "/". For example, '
                '"Massachusetts/Suffolk/Boston". <a href="https://dimagi.atlassian'
                '.net/wiki/spaces/commcarepublic/pages/2215051298/Organization+Data'
                '+Management"target="_blank">Learn more</a>.'
            ],
        }
        self.assertEqual(report_filter.filter_context, expected_context)

    def test_case_status_report_filter_context(self):
        report_filter = CaseStatusPinnedFilter(
            self.request, self.domain_name, use_bootstrap5=True
        )
        expected_context = {
            'report_select2_config': {
                'select': {
                    'options': [
                        {'val': 'open', 'text': 'Only Open'},
                        {'val': 'closed', 'text': 'Only Closed'},
                    ],
                    'default_text': 'Show All',
                    'selected': '',
                    'placeholder': '',
                },
                'pagination': {
                    'enabled': False,
                    'url': None,
                    'handler': '',
                    'action': None,
                },
            },
        }
        self.assertEqual(report_filter.filter_context, expected_context)
