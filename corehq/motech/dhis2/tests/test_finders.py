import doctest

import corehq.motech.dhis2.finders


def test_doctests():
    results = doctest.testmod(corehq.motech.dhis2.finders)
    assert results.failed == 0
