from contextlib import contextmanager
from functools import partial, wraps
from unittest import TestCase

from corehq.tests.tools import nottest


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


@nottest
def testcontextmanager(func=None, /, before_class=False):
    """Decorator for creating test context managers

    This is a thin wrapper around `contextlib.contextmanager` that also
    works as a decorator for test classes.

    :param before_class: See `decorate_test_class`.

    Usage:
    ```py
        @testcontextmanager
        def context():
            print("start")
            yield
            print("stop")

        # context manager
        with context():
            print("inside")

        # test function decorator
        @context
        def test_func():
            print("inside")

        # class decorator
        @context
        class Test(TestCase):
            def test_method(self):
                print("inside")

        # test method decorator
        class Test(TestCase):
            @context
            def test_method(self):
                print("inside")
    ```
    """
    if func is None:
        return partial(testcontextmanager, before_class=before_class)

    @wraps(func)
    def wrapper(test_class_or_func=None, /, **kw):
        context = contextmanager(func)(**kw)
        if test_class_or_func is None:
            return context
        if isinstance(test_class_or_func, type):
            return decorate_test_class(context, test_class_or_func, before_class)
        return context(test_class_or_func)
    return wrapper


def decorate_test_class(context, class_, before_class=False):
    """Apply context manager to test class

    :param before_class: If True, the context manager will start before
        `setUpClass` is called when decorating a test class. Otherwise
        it will start after `setUpClass` is called (the default). In
        either case the context manager will be stopped with
        `addClassCleanup`.
    """
    @classmethod
    def setUpClass(cls):
        if before_class:
            add_context(context, cls)
            original_setup()
        else:
            original_setup()
            add_context(context, cls)

    assert issubclass(class_, TestCase), class_
    original_setup, class_.setUpClass = class_.setUpClass, setUpClass
    return class_
