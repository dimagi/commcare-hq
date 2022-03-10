import doctest
from nose.tools import assert_equal
from corehq.apps.app_manager import id_strings


def test_doctests():
    results = doctest.testmod(id_strings)
    assert_equal(results.failed, 0)
