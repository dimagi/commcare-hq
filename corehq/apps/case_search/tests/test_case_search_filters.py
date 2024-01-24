from datetime import date

from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.case_search.models import FuzzyProperties, IgnorePatterns
from corehq.apps.case_search.tests.utils import get_case_search_query
from corehq.apps.es.tests.test_case_search_es import BaseCaseSearchTest
from corehq.apps.es.tests.utils import es_test


@es_test
class TestCaseSearchLookups(BaseCaseSearchTest):
    def test_date_range_criteria(self):
        self._create_case_search_config()
        self._assert_query_runs_correctly(
            self.domain,
            [
                {'_id': 'c1', 'dob': date(2020, 3, 1)},
                {'_id': 'c2', 'dob': date(2020, 3, 2)},
                {'_id': 'c3', 'dob': date(2020, 3, 3)},
                {'_id': 'c4', 'dob': date(2020, 3, 4)},
            ],
            get_case_search_query(
                self.domain,
                [self.case_type],
                {'dob': '__range__2020-03-02__2020-03-03'},
            ),
            None,
            ['c2', 'c3']
        )

    def test_fuzzy_properties(self):
        cases = [
            {'_id': 'c1', 'case_type': 'song', 'description': 'New York'},
            {'_id': 'c2', 'case_type': 'song', 'description': 'Neu York'},
            {'_id': 'c3', 'case_type': 'show', 'description': 'Boston'},
        ]
        config = self._create_case_search_config()
        fuzzy_properties = FuzzyProperties.objects.create(
            domain=self.domain,
            case_type='song',
            properties=['description'],
        )
        config.fuzzy_properties.add(fuzzy_properties)
        self.addCleanup(fuzzy_properties.delete)
        self._assert_query_runs_correctly(
            self.domain,
            cases,
            get_case_search_query(self.domain, ['song', 'show'], {'description': 'New York'}),
            None,
            ['c1', 'c2']
        )

    def test_ignore_patterns(self):
        cases = [
            {'_id': 'c1', 'case_type': 'person', 'phone_number': '8675309'},
            {'_id': 'c2', 'case_type': 'person', 'phone_number': '9045555555'},
        ]
        config = self._create_case_search_config()
        pattern = IgnorePatterns.objects.create(
            domain=self.domain, case_type='person', case_property='phone_number', regex="+1")
        config.ignore_patterns.add(pattern)
        self.addCleanup(pattern.delete)
        self._assert_query_runs_correctly(
            self.domain,
            cases,
            get_case_search_query(self.domain, ['person'], {'phone_number': '+18675309'}),
            None,
            ['c1']
        )

    def test_multiple_case_types(self):
        cases = [
            {'_id': 'c1', 'case_type': 'song', 'description': 'New York'},
            {'_id': 'c2', 'case_type': 'song', 'description': 'Another Song'},
            {'_id': 'c3', 'case_type': 'show', 'description': 'New York'},
            {'_id': 'c4', 'case_type': 'show', 'description': 'Boston'},
        ]
        self._create_case_search_config()
        self._assert_query_runs_correctly(
            self.domain,
            cases,
            get_case_search_query(self.domain, ['show', 'song'], {'description': 'New York'}),
            None,
            ['c1', 'c3']
        )

    def test_blank_case_search(self):
        # foo = '' should match all cases where foo is empty or absent
        self._create_case_search_config()
        self._bootstrap_cases_in_es_for_domain(self.domain, [
            {'_id': 'c1', 'foo': 'redbeard'},
            {'_id': 'c2', 'foo': 'blackbeard'},
            {'_id': 'c3', 'foo': ''},
            {'_id': 'c4'},
        ])
        for criteria, expected in [
            ({'foo': ''}, ['c3', 'c4']),
            ({'foo': ['', 'blackbeard']}, ['c2', 'c3', 'c4']),
        ]:
            actual = get_case_search_query(self.domain, [self.case_type], criteria).get_ids()
            msg = f"{criteria} yielded {actual}, not {expected}"
            self.assertItemsEqual(actual, expected, msg=msg)

    def test_blank_case_search_parent(self):
        self._create_case_search_config()
        self._bootstrap_cases_in_es_for_domain(self.domain, [
            {'_id': 'c1', 'foo': 'redbeard'},
            {'_id': 'c2', 'case_type': 'child', 'index': {'parent': (self.case_type, 'c1')}},
            {'_id': 'c3', 'foo': 'blackbeard'},
            {'_id': 'c4', 'case_type': 'child', 'index': {'parent': (self.case_type, 'c3')}},
            {'_id': 'c5', 'foo': ''},
            {'_id': 'c6', 'case_type': 'child', 'index': {'parent': (self.case_type, 'c5')}},
            {'_id': 'c7'},
            {'_id': 'c8', 'case_type': 'child', 'index': {'parent': (self.case_type, 'c7')}},
        ])
        actual = get_case_search_query(self.domain, ['child'], {
            'parent/foo': ['', 'blackbeard'],
        }).get_ids()
        self.assertItemsEqual(actual, ['c4', 'c6', 'c8'])

    def test_selected_any_function(self):
        self._create_case_search_config()
        cases = [
            {'_id': 'c1', 'case_type': 'song', 'description': 'New York'},
            {'_id': 'c2', 'case_type': 'song', 'description': 'Manchester'},
            {'_id': 'c3', 'case_type': 'song', 'description': 'Manchester Boston'},
        ]
        self._assert_query_runs_correctly(
            self.domain,
            cases,
            get_case_search_query(
                self.domain,
                ['song'],
                {'_xpath_query': "selected-any(description, 'New York Boston')"},
            ),
            None,
            ['c1', 'c3']
        )

    def test_selected_all_function(self):
        self._create_case_search_config()
        cases = [
            {'_id': 'c1', 'case_type': 'song', 'description': 'New York'},
            {'_id': 'c2', 'case_type': 'song', 'description': 'Manchester'},
            {'_id': 'c3', 'case_type': 'song', 'description': 'New York Boston'},
            {'_id': 'c4', 'case_type': 'song', 'description': 'New York Manchester'},
            {'_id': 'c5', 'case_type': 'song', 'description': 'New York Manchester Boston'},
        ]
        self._assert_query_runs_correctly(
            self.domain,
            cases,
            get_case_search_query(
                self.domain,
                ['song'],
                {'_xpath_query': "selected-all(description, 'New York Boston')"},
            ),
            None,
            ['c3', 'c5']
        )

    def test_selected_any_function_string_prop_name(self):
        self._create_case_search_config()
        cases = [
            {'_id': 'c1', 'case_type': 'song', 'description': 'New York'},
            {'_id': 'c2', 'case_type': 'song', 'description': 'Manchester'},
            {'_id': 'c3', 'case_type': 'song', 'description': 'Manchester Boston'},
        ]
        self._assert_query_runs_correctly(
            self.domain,
            cases,
            get_case_search_query(
                self.domain,
                ['song'],
                {'_xpath_query': "selected-any('description', 'New York Boston')"},
            ),
            None,
            ['c1', 'c3']
        )

    def test_selected_validate_property_name(self):
        with self.assertRaises(XPathFunctionException):
            get_case_search_query(
                self.domain,
                ['song'],
                {'_xpath_query': "selected-all(3, 'New York Boston')"},
            )

    def test_index_case_search(self):
        self._create_case_search_config()
        self._bootstrap_cases_in_es_for_domain(self.domain, [
            {'_id': 'c1', 'foo': 'redbeard'},
            {'_id': 'c2', 'case_type': 'child', 'index': {'parent': (self.case_type, 'c1')}},
            {'_id': 'c3', 'case_type': 'child', 'index': {'parent': (self.case_type, 'c1')}},
            {'_id': 'c4', 'case_type': 'child', 'index': {'host': (self.case_type, 'c1')}},
        ])
        actual = get_case_search_query(self.domain, ['child'], {
            'indices.parent': ['c1'],
        }).get_ids()
        self.assertItemsEqual(actual, ['c2', 'c3'])

        actual = get_case_search_query(self.domain, ['child'], {
            'indices.host': ['c1'],
        }).get_ids()
        self.assertItemsEqual(actual, ['c4'])

    def test_match_all(self):
        self._create_case_search_config()
        cases = [
            {'_id': 'c1', 'case_type': 'song', 'description': 'New York'},
            {'_id': 'c2', 'case_type': 'song', 'description': 'Manchester'},
            {'_id': 'c3', 'case_type': 'song', 'description': 'Manchester Boston'},
        ]
        self._assert_query_runs_correctly(
            self.domain,
            cases,
            get_case_search_query(
                self.domain,
                ['song'],
                {'_xpath_query': "match-all()"},
            ),
            None,
            ['c1', 'c2', 'c3']
        )

    def test_match_none(self):
        self._create_case_search_config()
        cases = [
            {'_id': 'c1', 'case_type': 'song', 'description': 'New York'},
            {'_id': 'c2', 'case_type': 'song', 'description': 'Manchester'},
            {'_id': 'c3', 'case_type': 'song', 'description': 'Manchester Boston'},
        ]
        self._assert_query_runs_correctly(
            self.domain,
            cases,
            get_case_search_query(
                self.domain,
                ['song'],
                {'_xpath_query': "match-none()"},
            ),
            None,
            []
        )
