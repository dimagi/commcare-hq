from unittest import mock

import pytest
from django.http import QueryDict
from django.test import RequestFactory, TestCase
from testil import eq

from corehq.apps.data_cleaning.exceptions import UnsupportedFilterValueException
from corehq.apps.data_cleaning.filters import (
    CaseOwnersPinnedFilter,
    CaseStatusPinnedFilter,
)
from corehq.apps.data_cleaning.models import (
    BulkEditFilter,
    BulkEditSession,
    DataType,
    FilterMatchType,
    PinnedFilterType,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import CaseSearchES
from corehq.apps.es import cases as case_es
from corehq.apps.es.case_search import (
    case_property_missing,
    case_search_adapter,
    exact_case_property_text_query,
)
from corehq.apps.es.client import manager
from corehq.apps.es.groups import group_adapter
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
)
from corehq.apps.es.users import user_adapter
from corehq.apps.hqwebapp.tests.tables.generator import get_case_blocks
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard.cases.utils import (
    deactivated_case_owners,
    get_case_owners,
    query_location_restricted_cases,
)
from corehq.apps.reports.tests.standard.cases.test_utils import BaseCaseOwnersTest
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.tests.utils import FormProcessorTestUtils


@pytest.mark.parametrize(
    ('category', 'valid_match_types'),
    [
        (
            DataType.FILTER_CATEGORY_TEXT,
            (
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
            ),
        ),
        (
            DataType.FILTER_CATEGORY_NUMBER,
            (
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
            ),
        ),
        (
            DataType.FILTER_CATEGORY_DATE,
            (
                FilterMatchType.EXACT,
                FilterMatchType.LESS_THAN,
                FilterMatchType.LESS_THAN_EQUAL,
                FilterMatchType.GREATER_THAN,
                FilterMatchType.GREATER_THAN_EQUAL,
                FilterMatchType.IS_EMPTY,
                FilterMatchType.IS_NOT_EMPTY,
                FilterMatchType.IS_MISSING,
                FilterMatchType.IS_NOT_MISSING,
            ),
        ),
        (
            DataType.FILTER_CATEGORY_MULTI_SELECT,
            (
                FilterMatchType.IS_ANY,
                FilterMatchType.IS_NOT_ANY,
                FilterMatchType.IS_ALL,
                FilterMatchType.IS_NOT_ALL,
                FilterMatchType.IS_EMPTY,
                FilterMatchType.IS_NOT_EMPTY,
                FilterMatchType.IS_MISSING,
                FilterMatchType.IS_NOT_MISSING,
            ),
        ),
    ],
)
def test_data_and_match_type_validation(category, valid_match_types):
    for data_type in DataType.FILTER_CATEGORY_DATA_TYPES[category]:
        for match_type, _ in FilterMatchType.ALL_CHOICES:
            is_valid = BulkEditFilter.is_data_and_match_type_valid(match_type, data_type)
            if match_type in valid_match_types:
                eq(is_valid, True, text=f'FilterMatchType {match_type} should support DataType {data_type}')
            else:
                eq(is_valid, False, text=f'FilterMatchType {match_type} should NOT support DataType {data_type}')


@es_test(requires=[case_search_adapter], setup_class=True)
class BulkEditFilterQueryTests(TestCase):
    domain = 'column-test-filters'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.web_user = WebUser.create(cls.domain, 'tester@datacleaning.org', 'testpwd', None, None)
        cls.addClassCleanup(cls.web_user.delete, cls.domain, deleted_by=None)

        case_search_es_setup(cls.domain, get_case_blocks())

    def setUp(self):
        super().setUp()
        self.session = BulkEditSession.objects.new_case_session(
            self.web_user.get_django_user(),
            self.domain,
            'plants',
        )

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDownClass()

    def test_filter_query_is_empty(self):
        query = CaseSearchES().domain(self.domain)
        for data_type, _ in DataType.CHOICES:
            with self.subTest(data_type=data_type):
                active_filter = BulkEditFilter(
                    session=self.session,
                    prop_id='soil_contents',
                    data_type=data_type,
                    match_type=FilterMatchType.IS_EMPTY,
                )
                filtered_query = active_filter.filter_query(query)
                expected_query = query.filter(exact_case_property_text_query('soil_contents', ''))
                assert filtered_query.es_query == expected_query.es_query

    def test_filter_query_is_not_empty(self):
        query = CaseSearchES().domain(self.domain)
        for data_type, _ in DataType.CHOICES:
            with self.subTest(data_type=data_type):
                active_filter = BulkEditFilter(
                    session=self.session,
                    prop_id='soil_contents',
                    data_type=data_type,
                    match_type=FilterMatchType.IS_NOT_EMPTY,
                )
                filtered_query = active_filter.filter_query(query)
                expected_query = query.NOT(exact_case_property_text_query('soil_contents', ''))
                assert filtered_query.es_query == expected_query.es_query

    def test_filter_query_is_missing(self):
        query = CaseSearchES().domain(self.domain)
        for data_type, _ in DataType.CHOICES:
            with self.subTest(data_type=data_type):
                active_filter = BulkEditFilter(
                    session=self.session,
                    prop_id='soil_contents',
                    data_type=data_type,
                    match_type=FilterMatchType.IS_MISSING,
                )
                filtered_query = active_filter.filter_query(query)
                expected_query = query.filter(case_property_missing('soil_contents'))
                assert filtered_query.es_query == expected_query.es_query

    def test_filter_query_is_not_missing(self):
        query = CaseSearchES().domain(self.domain)
        for data_type, _ in DataType.CHOICES:
            with self.subTest(data_type=data_type):
                active_filter = BulkEditFilter(
                    session=self.session,
                    prop_id='soil_contents',
                    data_type=data_type,
                    match_type=FilterMatchType.IS_NOT_MISSING,
                )
                filtered_query = active_filter.filter_query(query)
                expected_query = query.NOT(case_property_missing('soil_contents'))
                assert filtered_query.es_query == expected_query.es_query

    def filter_query_remains_unchanged_for_other_match_types(self):
        query = CaseSearchES().domain(self.domain)
        for match_type, _ in FilterMatchType.ALL_CHOICES:
            if match_type in dict(FilterMatchType.ALL_DATA_TYPES_CHOICES):
                continue
            for data_type, _ in DataType.CHOICES:
                with self.subTest(data_type=data_type, match_type=match_type):
                    active_filter = BulkEditFilter(
                        session=self.session,
                        prop_id='soil_contents',
                        data_type=data_type,
                        match_type=match_type,
                    )
                    filtered_query = active_filter.filter_query(query)
                    assert filtered_query.es_query is query.es_query


class BulkEditFilterXpathTest(TestCase):
    def test_exact_text_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.EXACT,
            value='Riny Iola',
        )
        assert active_filter.get_xpath_expression() == "name = 'Riny Iola'"

    def test_single_quote_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.EXACT,
            value="Happy's",
        )
        assert active_filter.get_quoted_value(active_filter.value) == '''"Happy's"'''
        assert active_filter.get_xpath_expression() == '''name = "Happy's"'''

    def test_double_quote_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.EXACT,
            value='Zesty "orange" Flora',
        )
        assert active_filter.get_quoted_value(active_filter.value) == """'Zesty "orange" Flora'"""
        assert active_filter.get_xpath_expression() == """name = 'Zesty "orange" Flora'"""

    def test_mixed_quote_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.EXACT,
            value="""Zesty's "orange" Flora""",
        )
        with pytest.raises(UnsupportedFilterValueException):
            active_filter.get_quoted_value(active_filter.value)
        with pytest.raises(UnsupportedFilterValueException):
            active_filter.get_xpath_expression()

    def test_exact_number_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='height_cm', data_type=DataType.DECIMAL, match_type=FilterMatchType.EXACT, value='11.2'
        )
        assert active_filter.get_xpath_expression() == 'height_cm = 11.2'

    def test_exact_date_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='watered_on', data_type=DataType.DATE, match_type=FilterMatchType.EXACT, value='2024-12-11'
        )
        assert active_filter.get_xpath_expression() == "watered_on = '2024-12-11'"

    def test_is_not_text_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='phone_num',
            data_type=DataType.PHONE_NUMBER,
            match_type=FilterMatchType.IS_NOT,
            value='11245523233',
        )
        assert active_filter.get_xpath_expression() == "phone_num != '11245523233'"

    def test_is_not_number_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='num_leaves',
            data_type=DataType.INTEGER,
            match_type=FilterMatchType.IS_NOT,
            value='5',
        )
        assert active_filter.get_xpath_expression() == 'num_leaves != 5'

    def test_less_than_number_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='height_cm',
            data_type=DataType.DECIMAL,
            match_type=FilterMatchType.LESS_THAN,
            value='12.35',
        )
        assert active_filter.get_xpath_expression() == 'height_cm < 12.35'

    def test_less_than_date_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='watered_on',
            data_type=DataType.DATETIME,
            match_type=FilterMatchType.LESS_THAN,
            value='2025-02-03 16:43',
        )
        assert active_filter.get_xpath_expression() == "watered_on < '2025-02-03 16:43'"

    def test_less_than_equal_number_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='weight_kg',
            data_type=DataType.DECIMAL,
            match_type=FilterMatchType.LESS_THAN_EQUAL,
            value='35.5',
        )
        assert active_filter.get_xpath_expression() == 'weight_kg <= 35.5'

    def test_less_than_equal_date_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='last_modified',
            data_type=DataType.DATETIME,
            match_type=FilterMatchType.LESS_THAN_EQUAL,
            value='2025-02-20 16:55',
        )
        assert active_filter.get_xpath_expression() == "last_modified <= '2025-02-20 16:55'"

    def test_greater_than_number_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='amount',
            data_type=DataType.INTEGER,
            match_type=FilterMatchType.GREATER_THAN,
            value='15',
        )
        assert active_filter.get_xpath_expression() == 'amount > 15'

    def test_greater_than_date_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='modified_on',
            data_type=DataType.DATE,
            match_type=FilterMatchType.GREATER_THAN,
            value='2025-01-22',
        )
        assert active_filter.get_xpath_expression() == "modified_on > '2025-01-22'"

    def test_greater_than_equal_number_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='num_branches',
            data_type=DataType.INTEGER,
            match_type=FilterMatchType.GREATER_THAN_EQUAL,
            value='23',
        )
        assert active_filter.get_xpath_expression() == 'num_branches >= 23'

    def test_greater_than_equal_date_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='submitted_on',
            data_type=DataType.DATE,
            match_type=FilterMatchType.GREATER_THAN_EQUAL,
            value='2025-03-03',
        )
        assert active_filter.get_xpath_expression() == "submitted_on >= '2025-03-03'"

    def test_starts_with_text_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.STARTS,
            value='st',
        )
        assert active_filter.get_xpath_expression() == "starts-with(name, 'st')"

    def test_starts_with_text_single_quote_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.STARTS,
            value="st's",
        )
        assert active_filter.get_xpath_expression() == """starts-with(name, "st's")"""

    def test_starts_with_text_double_quote_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.STARTS,
            value='st"s',
        )
        assert active_filter.get_xpath_expression() == """starts-with(name, 'st"s')"""

    def test_starts_text_mixed_quote_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='name',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.STARTS,
            value="""st"s m'd""",
        )
        with pytest.raises(UnsupportedFilterValueException):
            active_filter.get_xpath_expression()

    def test_starts_not_text_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='favorite_park',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.STARTS_NOT,
            value='fo',
        )
        assert active_filter.get_xpath_expression() == "not(starts-with(favorite_park, 'fo'))"

    def test_fuzzy_text_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='pot_type',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.FUZZY,
            value='ceremic',
        )
        assert active_filter.get_xpath_expression() == "fuzzy-match(pot_type, 'ceremic')"

    def test_fuzzy_not_text_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='pot_type',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.FUZZY_NOT,
            value='ceremic',
        )
        assert active_filter.get_xpath_expression() == "not(fuzzy-match(pot_type, 'ceremic'))"

    def test_phonetic_text_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='light_level',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.PHONETIC,
            value='hi',
        )
        assert active_filter.get_xpath_expression() == "phonetic-match(light_level, 'hi')"

    def test_phonetic_not_text_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='light_level',
            data_type=DataType.TEXT,
            match_type=FilterMatchType.PHONETIC_NOT,
            value='hi',
        )
        assert active_filter.get_xpath_expression() == "not(phonetic-match(light_level, 'hi'))"

    def test_is_any_text_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='health_issues',
            data_type=DataType.MULTIPLE_OPTION,
            match_type=FilterMatchType.IS_ANY,
            value='yellow_leaves root_rot',
        )
        assert active_filter.get_xpath_expression() == "selected-any(health_issues, 'yellow_leaves root_rot')"

    def test_is_not_any_text_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='health_issues',
            data_type=DataType.MULTIPLE_OPTION,
            match_type=FilterMatchType.IS_NOT_ANY,
            value='fungus root_rot',
        )
        assert active_filter.get_xpath_expression() == "not(selected-any(health_issues, 'fungus root_rot'))"

    def test_is_all_text_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='soil_contents',
            data_type=DataType.MULTIPLE_OPTION,
            match_type=FilterMatchType.IS_ALL,
            value='bark worm_castings',
        )
        assert active_filter.get_xpath_expression() == "selected-all(soil_contents, 'bark worm_castings')"

    def test_is_not_all_text_xpath(self):
        active_filter = BulkEditFilter(
            prop_id='soil_contents',
            data_type=DataType.MULTIPLE_OPTION,
            match_type=FilterMatchType.IS_NOT_ALL,
            value='bark worm_castings',
        )
        assert active_filter.get_xpath_expression() == "not(selected-all(soil_contents, 'bark worm_castings'))"

    def test_value_match_types_return_none_all_data_types_xpath(self):
        for match_type, _ in FilterMatchType.ALL_DATA_TYPES_CHOICES:
            for data_type, _ in DataType.CHOICES:
                with self.subTest(data_type=data_type, match_type=match_type):
                    active_filter = BulkEditFilter(
                        prop_id='a_property',
                        data_type=data_type,
                        match_type=match_type,
                    )
                    assert active_filter.get_xpath_expression() is None


class TestReportFilterSubclasses(TestCase):
    domain = 'report-filter-pinned-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.web_user = WebUser.create(cls.domain, 'tester@datacleaning.org', 'testpwd', None, None)
        cls.addClassCleanup(cls.web_user.delete, cls.domain, deleted_by=None)

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get('/cases/')
        self.request.domain = self.domain
        self.request.can_access_all_locations = True
        self.request.couch_user = self.web_user
        self.request.project = self.domain_obj
        self.session = BulkEditSession.objects.new_case_session(
            self.web_user.get_django_user(),
            self.domain,
            'plants',
        )

    def test_case_owners_report_filter_context(self):
        report_filter = CaseOwnersPinnedFilter(self.session, self.request, self.domain, use_bootstrap5=True)
        expected_context = {
            'report_select2_config': {
                'select': {
                    'options': [{'val': 't__0', 'text': '[Active Mobile Workers]'}],
                    'default_text': 'Filter by...',
                    'selected': [
                        {'id': 'all_data', 'text': '[All Data]'},
                    ],
                    'placeholder': 'Please add case owners to filter the list of cases.',
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
                '2143947350/Report+and+Export+Filters"'
                'target="_blank"> Filter Definitions</a>.',
            ],
        }
        assert report_filter.filter_context == expected_context

    @mock.patch.object(Domain, 'uses_locations', lambda: True)  # removes dependency on accounting
    def test_case_owners_report_filter_context_locations(self):
        report_filter = CaseOwnersPinnedFilter(self.session, self.request, self.domain, use_bootstrap5=True)
        expected_context = {
            'report_select2_config': {
                'select': {
                    'options': [{'val': 't__0', 'text': '[Active Mobile Workers]'}],
                    'default_text': 'Filter by...',
                    'selected': [
                        {'id': 'all_data', 'text': '[All Data]'},
                    ],
                    'placeholder': 'Please add case owners to filter the list of cases.',
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
                '2143947350/Report+and+Export+Filters"'
                'target="_blank"> Filter Definitions</a>.',
                'When searching by location, put your location name in quotes to '
                'show only exact matches. To more easily find a location, you may '
                'specify multiple levels by separating with a "/". For example, '
                '"Massachusetts/Suffolk/Boston". <a href="https://dimagi.atlassian'
                '.net/wiki/spaces/commcarepublic/pages/2215051298/Organization+Data'
                '+Management#Search-for-Locations"target="_blank">Learn more</a>.',
            ],
        }
        assert report_filter.filter_context == expected_context

    def test_case_owners_update_stored_value(self):
        self.request.POST = QueryDict('case_list_filter=project_data&case_list_filter=t__6&case_list_filter=t__3')
        self.request.method = 'POST'
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_OWNERS)
        assert pinned_filter.value is None
        report_filter = CaseOwnersPinnedFilter(self.session, self.request, self.domain, use_bootstrap5=True)
        report_filter.update_stored_value()
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_OWNERS)
        assert pinned_filter.value == ['project_data', 't__6', 't__3']
        expected_value = [
            {'id': 'project_data', 'text': '[Project Data]'},
            {'id': 't__6', 'text': '[Active Web Users]'},
            {'id': 't__3', 'text': '[Unknown Users]'},
        ]
        assert report_filter.filter_context['report_select2_config']['select']['selected'] == expected_value

    def test_case_status_report_filter_context(self):
        report_filter = CaseStatusPinnedFilter(self.session, self.request, self.domain, use_bootstrap5=True)
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
        assert report_filter.filter_context == expected_context

    def test_case_status_update_stored_value(self):
        self.request.POST = QueryDict('is_open=open')
        self.request.method = 'POST'
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_STATUS)
        assert pinned_filter.value is None
        report_filter = CaseStatusPinnedFilter(self.session, self.request, self.domain, use_bootstrap5=True)
        report_filter.update_stored_value()
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_STATUS)
        assert pinned_filter.value == ['open']
        assert report_filter.filter_context['report_select2_config']['select']['selected'] == 'open'


@es_test(requires=[case_search_adapter, user_adapter, group_adapter], setup_class=True)
class TestCaseOwnersPinnedFilterQuery(BaseCaseOwnersTest):
    domain = 'case-owners-pinned-filter-test-x1'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.deactivated_user = CommCareUser.create(cls.domain, 'deactivated-user-test', 'Passw0rd!', None, None)
        cls.deactivated_user.set_is_active(cls.domain, False)
        user_adapter.index(cls.deactivated_user)
        cls.deactivated_user.save()

        cls.web_location_user = WebUser.create(cls.domain, 'restricted@datacleaning.org', 'Passw0rd!', None, None)
        cls.web_location_user.set_location(cls.domain, cls.locations['Suffolk'])
        cls.restrict_user_to_assigned_locations(cls.web_location_user)
        cls.web_location_user.save()
        user_adapter.index(cls.web_location_user)

        cls.session_user = cls.web_users[0]

        case_search_es_setup(cls.domain, get_case_blocks())
        manager.index_refresh(user_adapter.index_name)
        manager.index_refresh(group_adapter.index_name)

    def setUp(self):
        super().setUp()
        self.session = BulkEditSession.objects.new_case_session(
            self.session_user.get_django_user(),
            self.domain,
            'plants',
        )
        self.session_location_restricted = BulkEditSession.objects.new_case_session(
            self.web_location_user.get_django_user(),
            self.domain,
            'plants',
        )

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()

        from couchdbkit import ResourceNotFound

        for user in [cls.deactivated_user, cls.web_location_user]:
            try:
                user.delete(cls.domain, None)
            except ResourceNotFound:
                pass

        super().tearDownClass()

    def test_default(self):
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_OWNERS)
        assert pinned_filter.value is None
        filtered_query = pinned_filter.filter_query(query)
        assert filtered_query.es_query == query.es_query

    def test_default_location_restricted(self):
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session_location_restricted.pinned_filters.get(
            filter_type=PinnedFilterType.CASE_OWNERS
        )
        assert pinned_filter.value is None
        filtered_query = pinned_filter.filter_query(query)
        expected_query = query_location_restricted_cases(query, self.domain, self.web_location_user)
        assert filtered_query.es_query == expected_query.es_query

    def test_all_data(self):
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_OWNERS)
        pinned_filter.value = ['project_data', 'all_data', 't__5']
        pinned_filter.save()
        filtered_query = pinned_filter.filter_query(query)
        assert filtered_query.es_query == query.es_query

    def test_all_data_location_restricted(self):
        # location restricted users can't view "all data", ensure that's the case
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session_location_restricted.pinned_filters.get(
            filter_type=PinnedFilterType.CASE_OWNERS
        )
        pinned_filter.value = ['project_data', 'all_data', 't__5']
        pinned_filter.save()
        filtered_query = pinned_filter.filter_query(query)
        expected_query = query_location_restricted_cases(query, self.domain, self.web_location_user)
        assert filtered_query.es_query == expected_query.es_query

    def test_deactivated(self):
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_OWNERS)
        pinned_filter.value = ['t__5']
        pinned_filter.save()
        expected_query = query.OR(deactivated_case_owners(self.domain))
        filtered_query = pinned_filter.filter_query(query)
        assert filtered_query.es_query == expected_query.es_query

    def test_deactivated_location_restricted(self):
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session_location_restricted.pinned_filters.get(
            filter_type=PinnedFilterType.CASE_OWNERS
        )
        pinned_filter.value = ['t__5']
        pinned_filter.save()
        expected_query = query_location_restricted_cases(query, self.domain, self.web_location_user)
        filtered_query = pinned_filter.filter_query(query)
        assert filtered_query.es_query == expected_query.es_query

    def test_selected_user_types(self):
        query = CaseSearchES().domain(self.domain)
        # HQUserType.DEACTIVATED is tested in test_deactivated
        # HQUserType.ACTIVE is not an option the filter (all mobile workers)
        for user_type, is_owners_empty in [
            (f't__{HQUserType.DEMO_USER}', False),
            (f't__{HQUserType.ADMIN}', True),  # not currently functional with get_case_owners()
            (f't__{HQUserType.UNKNOWN}', True),  # not currently functional with get_case_owners()
            (f't__{HQUserType.COMMTRACK}', False),
            (f't__{HQUserType.WEB}', False),
        ]:
            with self.subTest(user_type=user_type, is_owners_empty=is_owners_empty):
                pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_OWNERS)
                pinned_filter.value = [user_type]
                pinned_filter.save()
                filtered_query = pinned_filter.filter_query(query)
                expected_query = (
                    query
                    if is_owners_empty
                    else query.OR(case_es.owner(get_case_owners(True, self.domain, pinned_filter.value)))
                )
                assert filtered_query.es_query == expected_query.es_query

    def test_selected_user_types_location_restricted(self):
        query = CaseSearchES().domain(self.domain)
        # HQUserType.DEACTIVATED is tested in test_deactivated
        # HQUserType.ACTIVE is not an option the filter (all mobile workers)
        for user_type in [
            f't__{HQUserType.DEMO_USER}',
            f't__{HQUserType.ADMIN}',  # not currently functional with get_case_owners()
            f't__{HQUserType.UNKNOWN}',  # not currently functional with get_case_owners()
            f't__{HQUserType.COMMTRACK}',
            f't__{HQUserType.WEB}',
        ]:
            with self.subTest(user_type=user_type):
                pinned_filter = self.session_location_restricted.pinned_filters.get(
                    filter_type=PinnedFilterType.CASE_OWNERS
                )
                pinned_filter.value = [user_type]
                pinned_filter.save()
                filtered_query = pinned_filter.filter_query(query)
                expected_query = query_location_restricted_cases(query, self.domain, self.web_location_user)
                assert filtered_query.es_query == expected_query.es_query

    def test_selected_user_ids(self):
        selected_user_ids = [self.users[0]._id, self.users[3]._id, self.users[4]._id]
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_OWNERS)
        pinned_filter.value = [f'u__{user_id}' for user_id in selected_user_ids]
        pinned_filter.save()
        filtered_query = pinned_filter.filter_query(query)
        expected_query = query.OR(case_es.owner(get_case_owners(True, self.domain, pinned_filter.value)))
        assert filtered_query.es_query == expected_query.es_query

    def test_selected_user_ids_location_restricted(self):
        selected_user_ids = [self.users[0]._id, self.users[3]._id, self.users[4]._id]
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session_location_restricted.pinned_filters.get(
            filter_type=PinnedFilterType.CASE_OWNERS
        )
        pinned_filter.value = [f'u__{user_id}' for user_id in selected_user_ids]
        pinned_filter.save()
        filtered_query = pinned_filter.filter_query(query)
        expected_query = query_location_restricted_cases(
            query.OR(case_es.owner(get_case_owners(False, self.domain, pinned_filter.value))),
            self.domain,
            self.web_location_user,
        )
        assert filtered_query.es_query == expected_query.es_query

    def test_groups(self):
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_OWNERS)
        pinned_filter.value = [f'g__{self.group1._id}']
        pinned_filter.save()
        filtered_query = pinned_filter.filter_query(query)
        expected_query = query.OR(case_es.owner(get_case_owners(True, self.domain, pinned_filter.value)))
        assert filtered_query.es_query == expected_query.es_query

    def test_groups_location_restricted(self):
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session_location_restricted.pinned_filters.get(
            filter_type=PinnedFilterType.CASE_OWNERS
        )
        pinned_filter.value = [f'g__{self.group1._id}']
        pinned_filter.save()
        filtered_query = pinned_filter.filter_query(query)
        expected_query = query_location_restricted_cases(query, self.domain, self.web_location_user)
        assert filtered_query.es_query == expected_query.es_query

    def test_location_ids(self):
        location_id = self.locations['Brooklyn'].location_id
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_OWNERS)
        pinned_filter.value = [f'l__{location_id}']
        pinned_filter.save()
        filtered_query = pinned_filter.filter_query(query)
        expected_query = query.OR(case_es.owner(get_case_owners(True, self.domain, pinned_filter.value)))
        assert filtered_query.es_query == expected_query.es_query

    def test_location_ids_location_restricted(self):
        location_id = self.locations['Brooklyn'].location_id
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session_location_restricted.pinned_filters.get(
            filter_type=PinnedFilterType.CASE_OWNERS
        )
        pinned_filter.value = [f'l__{location_id}']
        pinned_filter.save()
        filtered_query = pinned_filter.filter_query(query)
        expected_query = query_location_restricted_cases(
            query.OR(case_es.owner(get_case_owners(False, self.domain, pinned_filter.value))),
            self.domain,
            self.web_location_user,
        )
        assert filtered_query.es_query == expected_query.es_query


@es_test(requires=[case_search_adapter], setup_class=True)
class TestCaseStatusPinnedFilterQuery(TestCase):
    domain = 'test-case-status-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.web_user = WebUser.create(cls.domain, 'tester@datacleaning.org', 'testpwd', None, None)
        cls.addClassCleanup(cls.web_user.delete, cls.domain, deleted_by=None)

        case_search_es_setup(cls.domain, get_case_blocks())

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.session = BulkEditSession.objects.new_case_session(
            self.web_user.get_django_user(),
            self.domain,
            'plants',
        )

    def test_default(self):
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_STATUS)
        assert pinned_filter.value is None
        filtered_query = pinned_filter.filter_query(query)
        assert filtered_query.es_query == query.es_query

    def test_open(self):
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_STATUS)
        pinned_filter.value = ['open']
        pinned_filter.save()
        filtered_query = pinned_filter.filter_query(query)
        expected_query = query.is_closed(False)
        assert filtered_query.es_query == expected_query.es_query

    def test_closed(self):
        query = CaseSearchES().domain(self.domain)
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_STATUS)
        pinned_filter.value = ['closed']
        pinned_filter.save()
        filtered_query = pinned_filter.filter_query(query)
        expected_query = query.is_closed(True)
        assert filtered_query.es_query == expected_query.es_query


class TestPinnedFilterDefaults(TestCase):
    domain = 'test-pinned-filter-defaults'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.web_user = WebUser.create(cls.domain, 'tester@datacleaning.org', 'testpwd', None, None)
        cls.addClassCleanup(cls.web_user.delete, cls.domain, deleted_by=None)

    def setUp(self):
        super().setUp()
        self.session = BulkEditSession.objects.new_case_session(
            self.web_user.get_django_user(),
            self.domain,
            'plants',
        )

    def test_default_pinned_filters(self):
        assert self.session.pinned_filters.count() == 2
        case_owners_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_OWNERS)
        assert case_owners_filter.value is None
        case_status_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_STATUS)
        assert case_status_filter.value is None


class TestBulkEditFilterManagers(TestCase):
    domain = 'test-bulk-edit-filter-managers'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.web_user = WebUser.create(cls.domain, 'tester@datacleaning.org', 'testpwd', None, None)
        cls.addClassCleanup(cls.web_user.delete, cls.domain, deleted_by=None)

    def setUp(self):
        super().setUp()
        self.session = BulkEditSession.objects.new_case_session(
            self.web_user.get_django_user(),
            self.domain,
            'plants',
        )

    def test_copy_filters_to_session(self):
        self.session.add_filter(
            'soil_contents',
            DataType.MULTIPLE_OPTION,
            FilterMatchType.IS_ANY,
            'bark worm_castings',
        )
        new_session = BulkEditSession.objects.new_case_session(
            self.web_user.get_django_user(),
            self.domain,
            'plants',
        )
        self.session.filters.copy_to_session(self.session, new_session)
        assert new_session.filters.count() == self.session.filters.count()
        other_session_filter = new_session.filters.first()
        assert other_session_filter.prop_id == 'soil_contents'
        assert other_session_filter.data_type == DataType.MULTIPLE_OPTION
        assert other_session_filter.match_type == FilterMatchType.IS_ANY
        assert other_session_filter.value == 'bark worm_castings'

    def test_copy_pinned_filters_to_session(self):
        pinned_filter = self.session.pinned_filters.get(filter_type=PinnedFilterType.CASE_STATUS)
        pinned_filter.value = ['open']
        pinned_filter.save()
        new_session = BulkEditSession.objects.new_case_session(
            self.web_user.get_django_user(),
            self.domain,
            'plants',
        )
        self.session.pinned_filters.copy_to_session(self.session, new_session)
        new_pinned_filter = new_session.pinned_filters.get(filter_type=PinnedFilterType.CASE_STATUS)
        assert new_pinned_filter.value == ['open']
