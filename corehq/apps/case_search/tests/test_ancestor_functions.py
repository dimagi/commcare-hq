from django.test import SimpleTestCase
from eulxml.xpath import parse as parse_xpath
from testil import eq

from corehq.apps.case_search.xpath_functions.ancestor_functions import is_ancestor_comparison, \
    _is_ancestor_path_expression
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
