from eulxml.xpath import parse as parse_xpath
from nose.tools import assert_raises_regex

from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.case_search.filter_dsl import (
    SearchFilterContext,
    build_filter_from_ast,
)

INVALID_TEST_CASES = [(
    'not(1 < 3, 2 < 4)',
    "The 'not' function accepts exactly 1 arguments, got 2"
), (
    'proximity(7)',
    "The 'proximity' function accepts exactly 4 arguments, got 1"
), (
    'proximity(7, "42.4402967 -71.1453275", 1, "miles")',
    "The first argument to 'proximity' must be a valid case property name"
), (
    'proximity("coords", 42.4402967, 1, "miles")',
    "The second argument to 'proximity' must be valid coordinates"
), (
    'proximity("coords", "42.4402967", 1, "miles")',
    "The second argument to 'proximity' must be valid coordinates"
), (
    'proximity("coords", "42.4402967 -71.1453275", 7, "smoots")',
    "is not a valid distance unit"
)]


def test_invalid():
    def _check(xpath, error_msg):
        with assert_raises_regex(XPathFunctionException, error_msg):
            parsed = parse_xpath(xpath)
            build_filter_from_ast(parsed, SearchFilterContext("mydomain"))

    for xpath, expected in INVALID_TEST_CASES:
        yield _check, xpath, expected
