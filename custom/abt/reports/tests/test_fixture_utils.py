import doctest

from nose.tools import assert_true

from custom.abt.reports import fixture_utils
from custom.abt.reports.fixture_utils import dict_values_in


def test_dict_values_in_param_none():
    swallow = {'permutation': 'unladen'}
    result = dict_values_in(swallow, None)
    assert_true(result)


def test_dict_values_in_value_none():
    swallow = {'permutation': 'unladen'}
    result = dict_values_in(swallow, {'permutation': None})
    assert_true(result)


def test_doctests():
    results = doctest.testmod(fixture_utils)
    assert results.failed == 0
