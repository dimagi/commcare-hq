import doctest


def test_doctests():
    import corehq.apps.events.es as module
    results = doctest.testmod(module, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
