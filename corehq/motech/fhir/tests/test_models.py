import doctest

from corehq.motech.fhir import models


def test_doctests():
    results = doctest.testmod(models, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
