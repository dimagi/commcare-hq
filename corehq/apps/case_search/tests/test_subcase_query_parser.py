from eulxml.xpath import parse as parse_xpath
from testil import eq, assert_raises

from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.case_search.xpath_functions.subcase_functions import _parse_normalize_subcase_query


def test_subcase_query_parsing():
    def _check(query, expected):
        node = parse_xpath(query)
        result = _parse_normalize_subcase_query(node)
        eq(result.as_tuple(), expected)

    yield from [
        (
            _check,
            "subcase-exists('parent', @case_type='bob')",
            ("parent", "@case_type='bob'", ">", 0, False)
        ),
        (
            _check,
            "subcase-exists('p', @case_type='bob' and prop='value')",
            ("p", "@case_type='bob' and prop='value'", ">", 0, False)
        ),
        (
            _check,
            "subcase-count('p', prop=1) > 3",
            ("p", "prop=1", ">", 3, False)
        ),
        (
            _check,
            "subcase-count('p', prop=1) >= 3",
            ("p", "prop=1", ">", 2, False)
        ),
        (
            _check,
            "subcase-count('p', prop=1) < 3",
            ("p", "prop=1", ">", 2, True)
        ),
        (
            _check,
            "subcase-count('p', prop=1) <= 3",
            ("p", "prop=1", ">", 3, True)
        ),
        (
            _check,
            "subcase-count('p', prop=1) = 3",
            ("p", "prop=1", "=", 3, False)
        ),
        (
            _check,
            "subcase-count('p', prop=1) = 0",
            ("p", "prop=1", ">", 0, True)
        ),
        (
            _check,
            "subcase-count('p', prop=1) != 2",
            ("p", "prop=1", "=", 2, True)
        ),
        (
            _check,
            "subcase-count('p') = 2",
            ("p", None, "=", 2, False)
        ),
        (
            _check,
            "subcase-exists('p')",
            ("p", None, ">", 0, False)
        ),
    ]


def test_subcase_query_parsing_validations():
    def _check(query, msg):
        node = parse_xpath(query)
        with assert_raises(XPathFunctionException, msg=msg):
            _parse_normalize_subcase_query(node)

    yield from [
        (
            _check,
            "subcase-exists()",
            "'subcase-exists' expects one or two arguments"
        ),
        (
            _check,
            "subcase-count() > 1",
            "'subcase-count' expects one or two arguments"
        ),
        (
            _check,
            "subcase-count()",
            "XPath incorrectly formatted. Expected 'subcase-exists'"
        ),
        (
            _check,
            "subcase-count('p', name = 'bob') > -1",
            "'subcase-count' must be compared to a positive integer"
        ),
        (
            _check,
            "subcase-count('p', name = 'bob') + 1",
            "Unsupported operator for use with 'subcase-count': +"
        ),
        (
            _check,
            "subcase-count('p', name = 'bob') > 'bob'",
            "'subcase-count' must be compared to a positive integer"
        ),
        (
            _check,
            "subcase-count('p', name = 'bob') > date('2020-01-01')",
            "'subcase-count' must be compared to a positive integer"
        ),
        (
            _check,
            "subcase-count(parent) = 1",
            "'subcase-count' error. Index identifier must be a string"
        ),
        (
            _check,
            "subcase-exists(3)",
            "'subcase-exists' error. Index identifier must be a string"
        ),
    ]
