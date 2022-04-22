from collections import Counter
from unittest.mock import patch

from testil import eq

from corehq.apps.app_manager.models import (
    Application,
    CaseSearchProperty,
    DetailColumn,
    Module,
)
from corehq.apps.case_search.utils import (
    _QueryHelper,
    get_related_case_relationships,
    get_related_case_results,
    get_related_cases,
)
from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import wrap_case_search_hit
from corehq.apps.es.tests.test_case_search_es import BaseCaseSearchTest
from corehq.apps.es.tests.utils import es_test


def test_get_related_case_relationships():
    app = Application.new_app("test-domain", "Case Search App")
    module = app.add_module(Module.new_module("Search Module", "en"))
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

    module = app.add_module(Module.new_module("Non-Search Module", "en"))
    module.case_type = "patient"
    detail = module.case_details.short
    detail.columns.append(
        DetailColumn(header={"en": "zz"}, model="case", field="parent/zz", format="plain"),
    )

    eq(get_related_case_relationships(app, "patient"), {"parent/parent", "host"})
    eq(get_related_case_relationships(app, "monster"), set())


@es_test
class TestGetRelatedCases(BaseCaseSearchTest):
    def test_get_related_case_results(self):
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

    def test_get_related_case_results_duplicates(self):
        """Test that `get_related_cases` does not include any cases that are in the initial
        set or are duplicates of others already found."""

        # d1 :> c2 > c1 > a1
        # d1 > c1
        # Search for case type 'c'
        # - initial results c1, c2
        # - related lookups (parent, parent/parent) yield a1, c1, a1
        # - child lookups yield c2, d1
        # - (future) extension lookups yield d1
        cases = [
            {'_id': 'a1', 'case_type': 'a'},
            {'_id': 'c1', 'case_type': 'c', 'index': {
                'parent': ('a', 'a1'),
            }},
            {'_id': 'c2', 'case_type': 'c', 'index': {
                'parent': ('c', 'c1'),
            }},
            {'_id': 'd1', 'case_type': 'd', 'index': {
                'parent': ('c', 'c1'),
                'host': ('c', 'c2'),
            }},
        ]
        self._bootstrap_cases_in_es_for_domain(self.domain, cases)

        hits = CaseSearchES().domain(self.domain).case_type("c").run().hits
        cases = [wrap_case_search_hit(result) for result in hits]
        self.assertEqual({case.case_id for case in cases}, {'c1', 'c2'})

        with patch("corehq.apps.case_search.utils.get_related_case_relationships",
                   return_value={"parent", "parent/parent"}), \
             patch("corehq.apps.case_search.utils.get_child_case_types", return_value={"c", "d"}), \
             patch("corehq.apps.case_search.utils.get_app_cached"):
            cases = get_related_cases(_QueryHelper(self.domain), None, {"c"}, cases, None)

        case_ids = Counter([case.case_id for case in cases])
        self.assertEqual(set(case_ids), {"a1", "d1"})  # c1, c2 excluded since they are in the initial list
        self.assertEqual(max(case_ids.values()), 1, case_ids)  # no duplicates

    def test_get_related_case_results_expanded_results(self):
        """Test that `get_related_cases` includes related cases for cases loaded
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
        cases = [wrap_case_search_hit(result) for result in hits]
        self.assertEqual({case.case_id for case in cases}, {'a1', 'a2', 'a3', 'a4'})

        with patch("corehq.apps.case_search.utils.get_related_case_relationships",
                   return_value={"parent"}), \
             patch("corehq.apps.case_search.utils.get_child_case_types", return_value={"c"}), \
             patch("corehq.apps.case_search.utils.get_app_cached"):
            cases = get_related_cases(_QueryHelper(self.domain), None, {"a"}, cases, 'custom_related_case_id')

        case_ids = Counter([case.case_id for case in cases])
        self.assertEqual(set(case_ids), {"b1", "p1", "c1"})
        self.assertEqual(max(case_ids.values()), 1, case_ids)  # no duplicates

    def _assert_related_case_ids(self, cases, paths, ids):
        results = get_related_case_results(_QueryHelper(self.domain), cases, paths)
        result_ids = Counter([result.case_id for result in results])
        self.assertEqual(ids, set(result_ids))
        if result_ids:
            self.assertEqual(1, max(result_ids.values()), result_ids)  # no duplicates
