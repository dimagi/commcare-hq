import doctest

from corehq.apps.translations import utils


def test_doctests():
    results = doctest.testmod(utils)
    assert results.failed == 0
