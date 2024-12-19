from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

import pytz
from eulxml.xpath import parse as parse_xpath
from freezegun import freeze_time

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure
from couchforms.geopoint import GeoPoint

from corehq.apps.case_search.exceptions import CaseFilterError
from corehq.apps.case_search.filter_dsl import (
    SearchFilterContext,
    build_filter_from_ast,
)
from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.case_search.utils import QueryHelper
from corehq.apps.es import filters
from corehq.apps.es.case_search import (
    CaseSearchES,
    case_property_date_range,
    case_property_geo_distance,
    case_property_missing,
    case_property_numeric_range,
    case_property_query,
    case_property_starts_with,
    case_search_adapter,
)
from corehq.apps.es.cases import case_name, is_closed
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.util.test_utils import flag_enabled


@es_test
class TestFilterDsl(ElasticTestMixin, SimpleTestCase):

    def test_simple_filter(self):
        parsed = parse_xpath("name = 'farid'")
        expected_filter = case_property_query('name', 'farid')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    @flag_enabled('CASE_SEARCH_INDEXED_METADATA')
    def test_simple_filter_optimized(self):
        parsed = parse_xpath("name = 'farid'")
        expected_filter = case_name('farid')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    @patch("corehq.apps.case_search.xpath_functions.comparison.get_timezone_for_domain",
           return_value=pytz.timezone('America/Los_Angeles'))
    def test_simple_filter_with_date(self, mock_get_timezone):
        parsed = parse_xpath("dob = '2023-06-03'")
        expected_filter = case_property_query('dob', '2023-06-03')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        mock_get_timezone.assert_not_called()
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    @patch("corehq.apps.case_search.xpath_functions.comparison.get_timezone_for_domain",
           return_value=pytz.timezone('America/Los_Angeles'))
    def test_datetime_system_property_filter(self, mock_get_timezone):
        parsed = parse_xpath("last_modified='2023-01-10'")
        expected_filter = case_property_date_range(
            'last_modified', gte='2023-01-10T08:00:00', lt='2023-01-11T08:00:00')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        mock_get_timezone.assert_called_once()
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    @flag_enabled('CASE_SEARCH_INDEXED_METADATA')
    @patch("corehq.apps.case_search.xpath_functions.comparison.get_timezone_for_domain",
           return_value=pytz.timezone('America/Los_Angeles'))
    def test_datetime_system_property_filter_optimized(self, mock_get_timezone):
        parsed = parse_xpath("last_modified='2023-01-10'")
        expected_filter = filters.date_range(
            'modified_on', gte='2023-01-10T08:00:00', lt='2023-01-11T08:00:00')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        mock_get_timezone.assert_called_once()
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    @freeze_time('2023-05-16T13:01:51Z')
    @flag_enabled('CASE_SEARCH_INDEXED_METADATA')
    def test_system_datetime_property_comparison(self):
        parsed = parse_xpath("last_modified < datetime-add(now(), 'weeks', -2)")
        expected_filter = filters.date_range('modified_on', lt='2023-05-02T13:01:51+00:00')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    @freeze_time('2023-05-16T13:01:51Z')
    @flag_enabled('CASE_SEARCH_INDEXED_METADATA')
    def test_system_datetime_property_match(self):
        parsed = parse_xpath("last_modified = now()")
        expected_filter = filters.term('modified_on', '2023-05-16T13:01:51+00:00')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_not_filter(self):
        parsed = parse_xpath("not(name = 'farid')")
        expected_filter = filters.NOT(case_property_query('name', 'farid'))
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    @flag_enabled('CASE_SEARCH_INDEXED_METADATA')
    def test_not_filter_optimized(self):
        parsed = parse_xpath("not(name = 'farid')")
        expected_filter = filters.NOT(case_name('farid'))
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_starts_with(self):
        parsed = parse_xpath("starts-with(ssn, '100')")
        expected_filter = case_property_starts_with('ssn', '100')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_date_comparison(self):
        parsed = parse_xpath("dob >= '2017-02-12'")
        expected_filter = case_property_date_range('dob', gte='2017-02-12')
        query = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter, query, is_raw_query=True)

    @freeze_time('2021-08-02')
    def test_date_comparison_today(self):
        parsed = parse_xpath("dob >= today()")
        expected_filter = case_property_date_range('dob', gte='2021-08-02')
        query = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter, query, is_raw_query=True)

    @freeze_time('2023-05-16T13:01:51Z')
    def test_date_property_comparison_now(self):
        parsed = parse_xpath("dob < datetime-add(now(), 'weeks', -2)")
        expected_filter = case_property_date_range('dob', lt='2023-05-02T13:01:51+00:00')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_numeric_comparison(self):
        parsed = parse_xpath("number <= '100.32'")
        expected_filter = case_property_numeric_range('number', lte=100.32)
        query = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter, query, is_raw_query=True)

    def test_numeric_comparison_negative(self):
        parsed = parse_xpath("number <= -100.32")
        expected_filter = case_property_numeric_range('number', lte=-100.32)
        query = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(expected_filter, query, is_raw_query=True)

    def test_numeric_equality_negative(self):
        parsed = parse_xpath("number = -100.32")
        expected_filter = case_property_query('number', -100.32)
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_case_property_existence(self):
        parsed = parse_xpath("property != ''")
        expected_filter = filters.NOT(case_property_missing('property'))
        query = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(query, expected_filter, is_raw_query=True)

    @flag_enabled('CASE_SEARCH_INDEXED_METADATA')
    def test_nested_filter(self):
        parsed = parse_xpath("(name = 'farid' or name = 'leila') and dob <= '2017-02-11'")
        expected_filter = filters.AND(
            filters.OR(case_name('farid'), case_name('leila')),
            case_property_date_range('dob', lte='2017-02-11'),
        )

        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_selected(self):
        parsed = parse_xpath("selected(first_name, 'Jon')")
        expected_filter_single = case_property_query('first_name', 'Jon', multivalue_mode='or')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter_single, is_raw_query=True)

        parsed = parse_xpath("selected(first_name, 'Jon John Jhon')")
        expected_filter_many = case_property_query('first_name', 'Jon John Jhon', multivalue_mode='or')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter_many, is_raw_query=True)

    def test_selected_any(self):
        parsed = parse_xpath("selected-any(first_name, 'Jon John Jhon')")
        expected_filter = case_property_query('first_name', 'Jon John Jhon', fuzzy=True)
        # Note fuzzy is on for this one
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain", fuzzy=True))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_selected_all(self):
        parsed = parse_xpath("selected-all(first_name, 'Jon John Jhon')")
        expected_filter = case_property_query('first_name', 'Jon John Jhon', multivalue_mode='and')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_self_reference(self):
        with self.assertRaises(CaseFilterError):
            build_filter_from_ast(parse_xpath("name = other_property"), SearchFilterContext("domain"))

        with self.assertRaises(CaseFilterError):
            build_filter_from_ast(parse_xpath("name > other_property"), SearchFilterContext("domain"))

        with self.assertRaises(CaseFilterError):
            build_filter_from_ast(parse_xpath("parent/name > other_property"), SearchFilterContext("domain"))

    @freeze_time('2021-08-02')
    def test_filter_today(self):
        parsed = parse_xpath("age > today()")
        expected_filter = case_property_date_range('age', gt='2021-08-02')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    @freeze_time('2021-08-02')
    def test_filter_date_today(self):
        parsed = parse_xpath("age > date(today())")
        expected_filter = case_property_date_range('age', gt='2021-08-02')
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_within_distance_filter(self):
        self._test_xpath_query(
            "within-distance(coords, '42.4402967 -71.1453275', 1, 'miles')",
            case_property_geo_distance('coords', GeoPoint(42.4402967, -71.1453275), miles=1.0)
        )

    def test_fuzzy_match(self):
        self._test_xpath_query(
            "fuzzy-match(name, 'jimmy')",
            case_property_query("name", "jimmy", fuzzy=True)
        )

    def test_fuzzy_date(self):
        self._test_xpath_query(
            "fuzzy-date(dob, '2024-12-03')",
            case_property_query("dob", [
                "2024-12-03",
                "2024-03-12",
                "2024-03-21",
                "2024-12-30",
                "2042-12-03",
                "2042-03-12",
                "2042-03-21",
                "2042-12-30"
            ], boost_first=True)
        )

    def _test_xpath_query(self, query_string, expected_filter):
        helper = QueryHelper("domain")
        helper.config = CaseSearchConfig(domain="domain")
        context = SearchFilterContext("domain", helper=helper)
        parsed = parse_xpath(query_string)
        built_filter = build_filter_from_ast(parsed, context)
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_match_all(self):
        parsed = parse_xpath("match-all()")
        expected_filter = filters.match_all()
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_match_none(self):
        parsed = parse_xpath("match-none()")
        expected_filter = filters.match_none()
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    @flag_enabled('CASE_SEARCH_INDEXED_METADATA')
    def test_status_query(self):
        parsed = parse_xpath("@status = 'open'")
        expected_filter = is_closed(False)
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    @flag_enabled('CASE_SEARCH_INDEXED_METADATA')
    def test_not_equals_query(self):
        parsed = parse_xpath("external_id != 'MyBadID'")
        expected_filter = filters.NOT(filters.term('external_id', 'MyBadID'))
        built_filter = build_filter_from_ast(parsed, SearchFilterContext("domain"))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)


@es_test(requires=[case_search_adapter], setup_class=True)
class TestFilterDslLookups(ElasticTestMixin, TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(TestFilterDslLookups, cls).setUpClass()
        cls.child_case1_id = 'margaery'
        cls.child_case2_id = 'loras'
        cls.parent_case_id = 'mace'
        cls.grandparent_case_id = 'olenna'
        cls.domain = "Tyrell"
        factory = CaseFactory(domain=cls.domain)
        grandparent_case = CaseStructure(
            case_id=cls.grandparent_case_id,
            attrs={
                'create': True,
                'case_type': 'grandparent',
                'update': {
                    "name": "Olenna",
                    "alias": "Queen of thorns",
                    "house": "Tyrell",
                },
            })

        parent_case = CaseStructure(
            case_id=cls.parent_case_id,
            attrs={
                'create': True,
                'case_type': 'parent',
                'update': {
                    "name": "Mace",
                    "house": "Tyrell",
                },
            },
            indices=[CaseIndex(
                grandparent_case,
                identifier='mother',
                relationship='child',
            )])

        child_case1 = CaseStructure(
            case_id=cls.child_case1_id,
            attrs={
                'create': True,
                'case_type': 'child',
                'update': {
                    "name": "Margaery",
                    "house": "Tyrell",
                },
            },
            indices=[CaseIndex(
                parent_case,
                identifier='father',
                relationship='extension',
            )],
        )
        child_case2 = CaseStructure(
            case_id=cls.child_case2_id,
            attrs={
                'create': True,
                'case_type': 'child',
                'update': {
                    "name": "Loras",
                    "house": "Tyrell",
                },
            },
            indices=[
                CaseIndex(
                    parent_case,
                    identifier='father',
                    relationship='extension',
                ),
                CaseIndex(
                    grandparent_case,
                    identifier='grandmother',
                    relationship='child',
                )
            ],
            walk_related=False,
        )
        for case in factory.create_or_update_cases([child_case1, child_case2]):
            case_search_adapter.index(case, refresh=True)

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDownClass()

    def test_parent_lookups(self):
        parsed = parse_xpath("father/name = 'Mace'")
        # return all the cases who's parent (relationship named 'father') has case property 'name' = 'Mace'

        expected_filter = {
            "nested": {
                "path": "indices",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "bool": {
                                    "filter": (
                                        {
                                            "terms": {
                                                "indices.referenced_id": [self.parent_case_id]
                                            }
                                        },
                                        {
                                            "term": {
                                                "indices.identifier": "father"
                                            }
                                        }
                                    )
                                }
                            }
                        ],
                        "must": {
                            "match_all": {}
                        }
                    }
                }
            }
        }
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)
        self.assertEqual([self.child_case1_id, self.child_case2_id], CaseSearchES().filter(
            built_filter).values_list('_id', flat=True))

    def test_nested_parent_lookups(self):
        parsed = parse_xpath("father/mother/house = 'Tyrell'")

        expected_filter = {
            "nested": {
                "path": "indices",
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "bool": {
                                    "filter": (
                                        {
                                            "terms": {
                                                "indices.referenced_id": [self.parent_case_id]
                                            }
                                        },
                                        {
                                            "term": {
                                                "indices.identifier": "father"
                                            }
                                        }
                                    )
                                }
                            }
                        ],
                        "must": {
                            "match_all": {}
                        }
                    }
                }
            }
        }
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)
        self.assertEqual([self.child_case1_id, self.child_case2_id], CaseSearchES().filter(
            built_filter).values_list('_id', flat=True))

    def test_subcase_exists(self):
        parsed = parse_xpath("subcase-exists('father', name='Margaery')")
        expected_filter = filters.doc_id([self.parent_case_id])
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_exists__filter_no_match(self):
        parsed = parse_xpath("subcase-exists('father', name='Mace')")
        expected_filter = filters.match_none()
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_exists__no_subase_filter(self):
        parsed = parse_xpath("subcase-exists('father')")
        expected_filter = filters.doc_id([self.parent_case_id])
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_exists_inverted(self):
        parsed = parse_xpath("not(subcase-exists('father', name='Margaery'))")
        expected_filter = filters.NOT(filters.doc_id([self.parent_case_id]))
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count__no_subcase_filter(self):
        parsed = parse_xpath("subcase-count('father') > 1")
        expected_filter = filters.doc_id([self.parent_case_id])
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count__filter_no_match(self):
        parsed = parse_xpath("subcase-count('father', house='Martel') > 0")
        expected_filter = filters.match_none()
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count_gt(self):
        parsed = parse_xpath("subcase-count('father', house='Tyrell') > 1")
        expected_filter = filters.doc_id([self.parent_case_id])
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count_lt(self):
        parsed = parse_xpath("subcase-count('father', house='Tyrell') < 1")
        expected_filter = filters.NOT(filters.doc_id([self.parent_case_id]))
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count_lt_no_match(self):
        """Subcase filter matches no cases and since it's an 'inverted' filter (lt)
        we don't need to apply any filtering to the parent query"""
        parsed = parse_xpath("subcase-count('father', house='Reyne') < 1")
        expected_filter = {"match_all": {}}
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count_no_match(self):
        parsed = parse_xpath("subcase-count('father', house='Tyrell') > 2")
        expected_filter = filters.match_none()
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_count_eq(self):
        parsed = parse_xpath("subcase-count('father', house='Tyrell') = 2")
        expected_filter = filters.doc_id([self.parent_case_id])
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_filter_relationship(self):
        parsed = parse_xpath("subcase-count('grandmother', house='Tyrell') >= 1")
        expected_filter = filters.doc_id([self.grandparent_case_id])
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)

    def test_subcase_filter_relationship_no_hits(self):
        parsed = parse_xpath("subcase-count('grandmother', house='Tyrell') > 1")
        expected_filter = filters.match_none()
        built_filter = build_filter_from_ast(parsed, SearchFilterContext(self.domain))
        self.checkQuery(built_filter, expected_filter, is_raw_query=True)
