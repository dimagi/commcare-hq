import doctest

from custom.abt.reports import late_pmt_2020


def test_doctests():
    results = doctest.testmod(late_pmt_2020)
    assert results.failed == 0
