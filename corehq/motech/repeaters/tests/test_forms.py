import doctest

from corehq.motech.repeaters import forms


def test_doctests():
    results = doctest.testmod(forms)
    assert results.failed == 0
