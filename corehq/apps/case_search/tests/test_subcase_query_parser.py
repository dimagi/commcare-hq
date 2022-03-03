from eulxml.xpath import parse as parse_xpath
from testil import eq

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
    ]
