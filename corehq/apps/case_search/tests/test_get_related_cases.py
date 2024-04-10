from collections import Counter
from unittest.mock import patch

from django.test import TestCase

from corehq.apps.app_manager.models import (
    Application,
    CaseSearchProperty,
    DetailColumn,
    DetailTab,
    Module,
)
from corehq.apps.case_search.const import IS_RELATED_CASE
from corehq.apps.case_search.utils import (
    _get_all_related_cases,
    _QueryHelper,
    get_and_tag_related_cases,
    get_child_case_results,
    get_child_case_types,
    get_path_related_cases_results,
    get_related_cases_result,
    get_search_detail_relationship_paths,
)
from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import wrap_case_search_hit
from corehq.apps.es.tests.test_case_search_es import BaseCaseSearchTest
from corehq.apps.es.tests.utils import es_test


class TestCaseSearchAppStuff(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.app = Application.new_app("test-domain", "Case Search App")
        module = cls.app.add_module(Module.new_module("Search Module", "en"))
        module.case_type = "patient"
        detail = module.case_details.short
        detail.columns.extend([
            DetailColumn(header={"en": "x"}, model="case", field="x", format="plain"),
            DetailColumn(header={"en": "y"}, model="case", field="parent/parent/y", format="plain"),
            DetailColumn(header={"en": "z"}, model="case", field="host/z", format="plain"),
        ])
        module.search_config.properties = [CaseSearchProperty(
            name="texture",
            label={"en": "Texture"},
        )]
        module.case_details.long.tabs = [
            DetailTab(starting_index=0),
            DetailTab(starting_index=1, has_nodeset=True, nodeset_case_type="child")
        ]

        module = cls.app.add_module(Module.new_module("Non-Search Module", "en"))
        module.case_type = "patient"
        detail = module.case_details.short
        detail.columns.append(
            DetailColumn(header={"en": "zz"}, model="case", field="parent/zz", format="plain"),
        )

    def test_get_search_detail_relationship_paths(self):
        self.assertEqual(get_search_detail_relationship_paths(self.app, ["patient"]),
                         {"parent/parent", "host"})
        self.assertEqual(get_search_detail_relationship_paths(self.app, ["monster"]), set())
        self.assertEqual(get_search_detail_relationship_paths(self.app, ["patient", "monster"]),
                         {"parent/parent", "host"})

    def test_get_child_case_types(self):
        self.assertEqual(get_child_case_types(self.app, "patient"), {'child'})
        self.assertEqual(get_child_case_types(self.app, "monster"), set())

@es_test
class TestGetRelatedCases(BaseCaseSearchTest):
    def test_get_path_related_cases_results(self):
        # Note that cases must be defined before other cases can reference them
        cases = [
            {'_id': 'c1', 'case_type': 'monster', 'description': 'grandparent of first person'},
            {'_id': 'c2', 'case_type': 'monster', 'description': 'parent of first person', 'index': {
                'parent': ('monster', 'c1')
            }},
            {'_id': 'c3', 'case_type': 'monster', 'description': 'parent of host'},
            {'_id': 'c4', 'case_type': 'monster', 'description': 'host of second person', 'index': {
                'parent': ('monster', 'c3')
            }},
            {'_id': 'c5', 'description': 'first person', 'index': {
                'parent': ('monster', 'c2')
            }},
            {'_id': 'c6', 'description': 'second person', 'index': {
                'host': ('monster', 'c4')
            }},
        ]
        self._bootstrap_cases_in_es_for_domain(self.domain, cases)

        hits = CaseSearchES().domain(self.domain).case_type(self.case_type).run().hits
        cases = [wrap_case_search_hit(result) for result in hits]
        self.assertEqual({case.case_id for case in cases}, {'c5', 'c6'})

        self._assert_related_case_ids(cases, set(), set())
        self._assert_related_case_ids(cases, {"parent"}, {"c2"})
        self._assert_related_case_ids(cases, {"host"}, {"c4"})
        self._assert_related_case_ids(cases, {"parent/parent"}, {"c1"})
        self._assert_related_case_ids(cases, {"host/parent"}, {"c3"})
        self._assert_related_case_ids(cases, {"host", "parent"}, {"c2", "c4"})
        self._assert_related_case_ids(cases, {"host", "parent/parent"}, {"c4", "c1"})

    def test_get_related_cases_duplicates_and_tags(self):
        """Test that `get_and_tag_related_cases` does not include any cases that are in the initial
        set or are duplicates of others already found."""

        # d1 :> c2 > c1 > a1
        # d1 > c1
        # c2 :> h1
        # Search for case type 'c'
        # - initial results c1, c2
        # - related lookups (parent, parent/parent) yield a1, c1, a1
        # - child lookups yield c2, d1
        # - extension lookups yield d1
        # - host lookups yield h1
        cases = [
            {'_id': 'a1', 'case_type': 'a'},
            {'_id': 'h1', 'case_type': 'h'},
            {'_id': 'c1', 'case_type': 'c', 'index': {
                'parent': ('a', 'a1'),
            }},
            {'_id': 'c2', 'case_type': 'c', 'index': {
                'parent': ('c', 'c1'),
                'host': ('h', 'h1', 'extension'),
            }},
            {'_id': 'd1', 'case_type': 'd', 'index': {
                'parent': ('c', 'c1'),
                'host': ('c', 'c2', 'extension'),
            }},
        ]
        self._bootstrap_cases_in_es_for_domain(self.domain, cases)

        hits = CaseSearchES().domain(self.domain).case_type("c").run().hits
        source_cases = [wrap_case_search_hit(result) for result in hits]
        self.assertEqual({case.case_id for case in source_cases}, {'c1', 'c2'})

        source_cases_related = {
            "PATH_RELATED_CASE_ID": {"a1"},  # c1 excluded since they are in the initial list
            "GRANDPARENT_CASE_ID": {"a1"},
            "PARENT_CASE_ID": {"a1"},  # c1 excluded since they are in the initial list
            "CHILD_CASE_ID": {"d1"},  # c2 excluded since they are in the initial list
            "HOST_ID": {"h1"},
            "EXT_ID": {"d1"}
        }

        def get_related_cases_helper(include_all_related_cases):
            with patch("corehq.apps.case_search.utils.get_search_detail_relationship_paths",
                    return_value={"parent", "parent/parent"}), \
                    patch("corehq.apps.case_search.utils.get_child_case_types", return_value={"c", "d"}), \
                    patch("corehq.apps.case_search.utils.get_app_cached"):

                return get_and_tag_related_cases(_QueryHelper(self.domain), None, {"c"}, source_cases, None,
                    include_all_related_cases)

        partial_related_cases = get_related_cases_helper(include_all_related_cases=False)
        EXPECTED_PARTIAL_RELATED_CASES = (source_cases_related["PATH_RELATED_CASE_ID"]
            | source_cases_related["CHILD_CASE_ID"])
        self._assert_case_ids(EXPECTED_PARTIAL_RELATED_CASES, partial_related_cases)
        self._assert_is_only_related_case_tag(source_cases, partial_related_cases)

        all_related_cases = get_related_cases_helper(include_all_related_cases=True)
        EXPECTED_ALL_RELATED_CASES = set().union(*source_cases_related.values())
        self._assert_case_ids(EXPECTED_ALL_RELATED_CASES, all_related_cases)
        self._assert_is_only_related_case_tag(source_cases, all_related_cases)

    def test_get_related_cases_expanded_results(self):
        """Test that `get_and_tag_related_cases` includes related cases for cases loaded
        via the 'custom_related_case_property'."""

        # Search for case type 'a'
        # - initial results a[1-4]
        # - expanded lookup yields b1
        # - related lookups (parent) yield p1 (b1 -> p1)
        # - child lookups yield c1 (b1 <- c1)
        cases = [
            {'_id': 'p1', 'case_type': 'p'},
            {'_id': 'a1', 'case_type': 'a'},
            {'_id': 'a2', 'case_type': 'a', 'custom_related_case_id': 'b1'},
            {'_id': 'a3', 'case_type': 'a', 'custom_related_case_id': 'b1'},
            {'_id': 'a4', 'case_type': 'a', 'custom_related_case_id': ''},
            {'_id': 'b1', 'case_type': 'b', 'index': {
                'parent': ('p', 'p1'),
            }},
            {'_id': 'c1', 'case_type': 'c', 'index': {
                'parent': ('b', 'b1'),
            }},
        ]
        self._bootstrap_cases_in_es_for_domain(self.domain, cases)

        hits = CaseSearchES().domain(self.domain).case_type("a").run().hits
        source_cases = [wrap_case_search_hit(result) for result in hits]
        self.assertEqual({case.case_id for case in source_cases}, {'a1', 'a2', 'a3', 'a4'})

        source_cases_related = {
            "EXPANDED_CASE_ID": {"b1"},
            "PATH_RELATED_CASE_ID": {"p1"},
            "CHILD_CASE_ID": {"c1"},
        }

        with patch("corehq.apps.case_search.utils.get_search_detail_relationship_paths",
                   return_value={"parent"}), \
                patch("corehq.apps.case_search.utils.get_child_case_types", return_value={'c'}), \
                patch("corehq.apps.case_search.utils.get_app_cached"):
            include_all_related_cases = False
            partial_related_cases = get_and_tag_related_cases(_QueryHelper(self.domain), None, {"a"}, source_cases,
                'custom_related_case_id', include_all_related_cases)

        EXPECTED_PARTIAL_RELATED_CASES = (source_cases_related["EXPANDED_CASE_ID"]
            | source_cases_related["PATH_RELATED_CASE_ID"]
            | source_cases_related["CHILD_CASE_ID"])
        self._assert_case_ids(EXPECTED_PARTIAL_RELATED_CASES, partial_related_cases)

    def test_get_child_case_results(self):
        # b1>a1
        # c1>a2
        # d1>b1
        cases = [
            {'_id': 'a1', 'case_type': 'a'},
            {'_id': 'a2', 'case_type': 'a'},
            {'_id': 'a3', 'case_type': 'a'},
            {'_id': 'a4', 'case_type': 'a'},
            {'_id': 'b1', 'case_type': 'b', 'index': {
                'parent': ('a', 'a1'),
            }},
            {'_id': 'c1', 'case_type': 'c', 'index': {
                'parent': ('a', 'a2'),
            }},
            {'_id': 'd1', 'case_type': 'd', 'index': {
                'parent': ('b', 'b1')
            }},
        ]
        self._bootstrap_cases_in_es_for_domain(self.domain, cases)

        SOURCE_CASE_ID = {'a1', 'a2', 'a3', 'a4'}
        RESULT_CHILD_CASE_ID = {'b1', 'c1'}
        CHILD_CASE_TYPE_FILTER = {'b'}
        WITH_FILTER_RESULT_CHILD_CASE_ID = {'b1'}

        result_cases = get_child_case_results(_QueryHelper(self.domain), SOURCE_CASE_ID)
        self._assert_case_ids(RESULT_CHILD_CASE_ID, result_cases)

        result_cases = get_child_case_results(_QueryHelper(self.domain), SOURCE_CASE_ID, CHILD_CASE_TYPE_FILTER)
        self._assert_case_ids(WITH_FILTER_RESULT_CHILD_CASE_ID, result_cases)

    def test__get_all_related_cases(self):
        """Test that `get_all_related_cases includes grandparent, parent, children, host, and
        extension cases related to the initial source cases"""
        # a1>b1>g1
        # e1:>a3:>h1>:h2
        # c1>a2
        cases = [
            {'_id': 'g1', 'case_type': 'g'},
            {'_id': 'b1', 'case_type': 'b', 'index': {
                'parent': ('g', 'g1'),
            }},
            {'_id': 'h2', 'case_type': 'g'},
            {'_id': 'h1', 'case_type': 'h', 'index': {
                'host': ('h', 'h2', 'extension'),
            }},
            {'_id': 'a1', 'case_type': 'a', 'index': {
                'parent': ('b', 'b1'),
            }},
            {'_id': 'a2', 'case_type': 'a'},
            {'_id': 'a3', 'case_type': 'a', 'index': {
                'host': ('h', 'h1', 'extension'),
            }},
            {'_id': 'c1', 'case_type': 'c', 'index': {
                'parent': ('a', 'a2'),
            }},
            {'_id': 'e1', 'case_type': 'e', 'index': {
                'host': ('a', 'a3', 'extension'),
            }},
        ]
        self._bootstrap_cases_in_es_for_domain(self.domain, cases)
        hits = CaseSearchES().domain(self.domain).case_type("a").run().hits
        source_cases = [wrap_case_search_hit(result) for result in hits]

        source_cases_related = {
            "GRANDPARENT_CASE_ID": {"g1", "h2"},
            "PARENT_CASE_ID": {"b1"},
            "CHILD_CASE_ID": {"c1"},
            "HOST_ID": {"h1"},
            "EXT_ID": {"e1"}
        }

        EXPECTED_ALL_RELATED_CASES = set().union(*source_cases_related.values())
        all_related_cases = _get_all_related_cases(_QueryHelper(self.domain), source_cases)
        self._assert_case_ids(EXPECTED_ALL_RELATED_CASES, all_related_cases)

    def test_get_related_cases_result(self):
        """Test that `get_related_cases_result` includes all cases when include_all_related_cases
        is True. And includes only child and path related cases when include_all_related_cases is False"""

        # a1>b1
        # c1>a2
        # e1:>a3
        cases = [
            {'_id': 'b1', 'case_type': 'b'},
            {'_id': 'a1', 'case_type': 'a', 'index': {
                'parent': ('b', 'b1'),
            }},
            {'_id': 'a2', 'case_type': 'a'},
            {'_id': 'a3', 'case_type': 'a'},
            {'_id': 'c1', 'case_type': 'c', 'index': {
                'parent': ('a', 'a2'),
            }},
            {'_id': 'e1', 'case_type': 'e', 'index': {
                'host': ('a', 'a3', 'extension'),
            }},
        ]
        self._bootstrap_cases_in_es_for_domain(self.domain, cases)
        hits = CaseSearchES().domain(self.domain).case_type("a").run().hits
        source_cases = [wrap_case_search_hit(result) for result in hits]

        source_cases_related = {
            "PATH_RELATED_CASE_ID": {"b1"},
            "PARENT_CASE_ID": {"b1"},
            "CHILD_CASE_ID": {"c1"},
            "EXT_ID": {"e1"},
        }

        def get_related_cases_result_helper(include_all_related_cases):
            with (patch("corehq.apps.case_search.utils.get_child_case_types", return_value={'c'}),
                  patch("corehq.apps.case_search.utils.get_search_detail_relationship_paths",
                        return_value={"parent"}),
                  patch("corehq.apps.case_search.utils.get_app_cached",
                        return_value=None)):
                return get_related_cases_result(_QueryHelper(self.domain), 'app_id', {'teacher'},
                    source_cases, include_all_related_cases)

        EXPECTED_PARTIAL_RELATED_CASES = (source_cases_related["PATH_RELATED_CASE_ID"]
            | source_cases_related["CHILD_CASE_ID"])
        partial_related_cases = get_related_cases_result_helper(include_all_related_cases=False)
        self._assert_case_ids(EXPECTED_PARTIAL_RELATED_CASES, partial_related_cases)

        EXPECTED_ALL_RELATED_CASES = set().union(*source_cases_related.values())
        all_related_cases = get_related_cases_result_helper(include_all_related_cases=True)
        self._assert_case_ids(EXPECTED_ALL_RELATED_CASES, all_related_cases)

    def _assert_related_case_ids(self, cases, paths, expected_case_ids):
        results = get_path_related_cases_results(_QueryHelper(self.domain), cases, paths)
        self._assert_case_ids(expected_case_ids, results)

    def _assert_case_ids(self, expected_case_ids, result_cases):
        result_ids = Counter([case.case_id for case in result_cases])
        self.assertEqual(expected_case_ids, set(result_ids))
        if result_ids:
            self.assertEqual(1, max(result_ids.values()), result_ids)  # no duplicates

    def _assert_is_only_related_case_tag(self, primary_cases, related_cases):
        for case in primary_cases:
            self.assertEqual(hasattr(case.case_json, IS_RELATED_CASE), False)
        for case in related_cases:
            self.assertEqual(case.case_json[IS_RELATED_CASE], 'true')
