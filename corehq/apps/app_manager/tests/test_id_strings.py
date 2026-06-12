import doctest
from corehq.apps.app_manager import id_strings


def test_doctests():
    results = doctest.testmod(id_strings)
    assert results.failed == 0
