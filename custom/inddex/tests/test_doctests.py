import doctest

import custom.inddex.reports.r4_nutrient_stats


def test_doctests():
    results = doctest.testmod(custom.inddex.reports.r4_nutrient_stats)
    assert results.failed == 0
