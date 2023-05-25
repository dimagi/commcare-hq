from django.test import SimpleTestCase
from eulxml.xpath import parse as parse_xpath
from testil import eq

from corehq.apps.case_search.xpath_functions.ancestor_functions import is_ancestor_comparison, \
    _is_ancestor_path_expression
from corehq.apps.case_search.tests.utils import get_case_search_query
from corehq.apps.es.tests.test_case_search_es import BaseCaseSearchTest
from corehq.apps.es.tests.utils import es_test
from corehq.util.test_utils import generate_cases


class TestIsAncestorPath(SimpleTestCase):
    @generate_cases([
        ("parent/name", False),
        ("parent/host/name", False),
        ("parent/host/@case_id", False),
        ("parent", False),
        ("parent = 'bob'", False),
        ("parent/name = 'bob'", True),
        ("parent/host/name = 'bob'", True),
    ])
    def test_is_ancestor_query(self, expression, expected):
        node = parse_xpath(expression)
        eq(is_ancestor_comparison(node), expected)

    @generate_cases([
        ("parent/name", True),
        ("parent/host/name", True),
        ("parent/host/parent/@case_id", True),
        ("parent", False),
        ("parent = 'bob'", False),
        ("parent/name = 'bob'", False),
        ("parent/host/name = 'bob'", False),
    ])
    def test_is_ancestor_path_expression(self, expression, expected):
        node = parse_xpath(expression)
        eq(_is_ancestor_path_expression(node), expected)


@es_test
class TestAncestorExists(BaseCaseSearchTest):
    def setUp(self):
        super(TestAncestorExists, self).setUp()
        self._create_case_search_config()
        # Note that cases must be defined before other cases can reference them
        # a1>p1(LA)>g1(CA)
        # a1>p1(LA):>h3(USA)
        # a2:>h1>(BOS):>h2(MA)
        # a2:>h1>(BOS)>g2(USA)
        # c1>a3
        cases = [
            {'_id': 'h3', 'country': 'USA', 'case_type': 'h'},
            {'_id': 'g2', 'country': 'USA', 'case_type': 'g'},
            {'_id': 'g1', 'state': 'CA', 'case_type': 'g'},
            {'_id': 'p1', 'city': 'LA', 'case_type': 'p', 'index': {
                'parent': ('g', 'g1'),
                'host': ('h', 'h3', 'extension'),
            }},
            {'_id': 'h2', 'state': 'MA', 'case_type': 'g'},
            {'_id': 'h1', 'city': 'BOS', 'case_type': 'h', 'index': {
                'host': ('h', 'h2', 'extension'),
                'parent': ('g', 'g2'),
            }},
            {'_id': 'a1', 'case_type': 'a', 'index': {
                'parent': ('p', 'p1'),
            }},
            {'_id': 'a3', 'case_type': 'a'},
            {'_id': 'a2', 'case_type': 'a', 'index': {
                'host': ('h', 'h1', 'extension'),
            }},
            {'_id': 'c1', 'city': 'SF', 'case_type': 'c', 'index': {
                'parent': ('a', 'a3'),
            }},
        ]
        self._bootstrap_cases_in_es_for_domain(self.domain, cases)

    def testparent(self):
        query1 = get_case_search_query(
            self.domain,
            ['a'],
            {'_xpath_query': "ancestor-exists(parent, city='LA')"},
        )
        self.assertItemsEqual(query1.get_ids(), ['a1'])

    def testparentparent(self):
        query1 = get_case_search_query(
            self.domain,
            ['a'],
            {'_xpath_query': "ancestor-exists(parent/parent, state='CA')"},
        )
        self.assertItemsEqual(query1.get_ids(), ['a1'])

    def testhost(self):
        query1 = get_case_search_query(
            self.domain,
            ['a'],
            {'_xpath_query': "ancestor-exists(host, city='BOS')"},
        )
        self.assertItemsEqual(query1.get_ids(), ['a2'])

    def testhosthost(self):
        query1 = get_case_search_query(
            self.domain,
            ['a'],
            {'_xpath_query': "ancestor-exists(host/host, state='MA')"},
        )
        self.assertItemsEqual(query1.get_ids(), ['a2'])

    def testhostparent(self):
        query1 = get_case_search_query(
            self.domain,
            ['a'],
            {'_xpath_query': "ancestor-exists(host/parent, country='USA')"},
        )
        self.assertItemsEqual(query1.get_ids(), ['a2'])

    def testparenthost(self):
        query1 = get_case_search_query(
            self.domain,
            ['a'],
            {'_xpath_query': "ancestor-exists(parent/host, country='USA')"},
        )
        self.assertItemsEqual(query1.get_ids(), ['a1'])
