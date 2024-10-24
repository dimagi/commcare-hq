from unittest import TestCase


def add_context(context_manager, testcase):
    """Enter context manager and ensure it is cleaned up on testcase teardown

    Context manager exit will be scheduled with `addClassCleanup()` if
    testcase is a subclass of `unittest.TestCase`. Otherwise it will be
    scheduled with `addCleanup()`.

    Returns the result of the entered context manager.
    """
    result = context_manager.__enter__()
    if isinstance(testcase, type) and issubclass(testcase, TestCase):
        testcase.addClassCleanup(context_manager.__exit__, None, None, None)
    else:
        testcase.addCleanup(context_manager.__exit__, None, None, None)
    return result
