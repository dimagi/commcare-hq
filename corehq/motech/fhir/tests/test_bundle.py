import doctest

from .. import bundle


def test_doctests():
    results = doctest.testmod(bundle, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
