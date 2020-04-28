import doctest


def test_doctests():
    from corehq.motech.dhis2 import schema

    results = doctest.testmod(schema)
    assert results.failed == 0
