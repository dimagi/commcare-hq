import doctest

from testil import eq

from corehq.motech.dhis2 import forms


def test_int_in_range():
    for args, expected_result in [
        (('5', 1, 7), True),
        (('five', 1, 7), False),
        ((42, 1, 7), False),
        ((None, 1, 7), False),
    ]:
        result = forms._int_in_range(*args)
        eq(result, expected_result)


def test_doctests():
    results = doctest.testmod(forms)
    assert results.failed == 0
