import doctest

from corehq.motech import finders


def test_doctests():
    results = doctest.testmod(finders)
    assert results.failed == 0
