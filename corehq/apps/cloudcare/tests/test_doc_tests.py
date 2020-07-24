import doctest

import corehq.apps.cloudcare.views


def test_view_doctests():
    results = doctest.testmod(corehq.apps.cloudcare.views)
    assert results.failed == 0, results
