import pytest
from eulxml.xpath import parse as parse_xpath
from testil import eq, assert_raises

from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.case_search.xpath_functions.subcase_functions import _parse_normalize_subcase_query


@pytest.mark.parametrize("query, expected", [
    (
        "subcase-exists('parent', @case_type='bob')",
        ("parent", "@case_type='bob'", ">", 0, False)
    ),
    (
        "subcase-exists('p', @case_type='bob' and prop='value')",
        ("p", "@case_type='bob' and prop='value'", ">", 0, False)
    ),
    (
        "subcase-count('p', prop=1) > 3",
        ("p", "prop=1", ">", 3, False)
    ),
    (
        "subcase-count('p', prop=1) >= 3",
        ("p", "prop=1", ">", 2, False)
    ),
    (
        "subcase-count('p', prop=1) < 3",
        ("p", "prop=1", ">", 2, True)
    ),
    (
        "subcase-count('p', prop=1) <= 3",
        ("p", "prop=1", ">", 3, True)
    ),
    (
        "subcase-count('p', prop=1) = 3",
        ("p", "prop=1", "=", 3, False)
    ),
    (
        "subcase-count('p', prop=1) = 0",
        ("p", "prop=1", ">", 0, True)
    ),
    (
        "subcase-count('p', prop=1) != 2",
        ("p", "prop=1", "=", 2, True)
    ),
    (
        "subcase-count('p') = 2",
        ("p", None, "=", 2, False)
    ),
    (
        "subcase-exists('p')",
        ("p", None, ">", 0, False)
    ),
])
def test_subcase_query_parsing(query, expected):
    node = parse_xpath(query)
    result = _parse_normalize_subcase_query(node)
    eq(result.as_tuple(), expected)


@pytest.mark.parametrize("query, msg", [
    (
        "subcase-exists()",
        "'subcase-exists' expects one or two arguments"
    ),
    (
        "subcase-count() > 1",
        "'subcase-count' expects one or two arguments"
    ),
    (
        "subcase-count()",
        "XPath incorrectly formatted. Expected 'subcase-exists'"
    ),
    (
        "subcase-count('p', name = 'bob') > -1",
        "'subcase-count' must be compared to a positive integer"
    ),
    (
        "subcase-count('p', name = 'bob') + 1",
        "Unsupported operator for use with 'subcase-count': +"
    ),
    (
        "subcase-count('p', name = 'bob') > 'bob'",
        "'subcase-count' must be compared to a positive integer"
    ),
    (
        "subcase-count('p', name = 'bob') > date('2020-01-01')",
        "'subcase-count' must be compared to a positive integer"
    ),
    (
        "subcase-count(parent) = 1",
        "'subcase-count' error. Index identifier must be a string"
    ),
    (
        "subcase-exists(3)",
        "'subcase-exists' error. Index identifier must be a string"
    ),
])
def test_subcase_query_parsing_validations(query, msg):
    node = parse_xpath(query)
    with assert_raises(XPathFunctionException, msg=msg):
        _parse_normalize_subcase_query(node)
