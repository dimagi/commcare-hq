"""warnings test utilities"""
import warnings
from functools import wraps
from unittest import TestCase

from corehq.tests.tools import nottest
from corehq.util.test_utils import unit_testing_only


@nottest
class TestContextDecorator:
    """Context manager/decorator for wrapping tests

    Initialize with a single context manager argument or override
    `__init__`, `__repr__`, `__enter__` and `__exit__`.
    """

    def __init__(self, context):
        self.context = context

    def __repr__(self):
        return f"{type(self).__name__}({self.context})"

    def __enter__(self):
        return self.context.__enter__()

    def __exit__(self, *exc_info):
        self.context.__exit__(*exc_info)

    def start(self):
        self.__enter__()

    def stop(self):
        self.__exit__(None, None, None)

    def __call__(self, func):
        if isinstance(func, type):
            assert issubclass(func, TestCase), func
            return self.decorate_class(func)
        return self.decorate_callable(func)

    def decorate_class(self, class_):
        @classmethod
        def setUpClass(cls):
            self.start()
            cls.addClassCleanup(self.stop)
            original_setup()

        original_setup, class_.setUpClass = class_.setUpClass, setUpClass
        return class_

    def decorate_callable(self, func):
        @wraps(func)
        def filtered(*args, **kw):
            with self:
                return func(*args, **kw)
        return filtered


class filter_warnings(TestContextDecorator):
    """Context manager/test decorator for temporarily filtering warnings

    A thin wrapper around `warnings.catch_warnings()` and
    `warnings.filterwarnings()`. Accepts the same arguments as
    `warnings.filterwarnings()`.

    Usage:
    ```py
        with filter_warnings("default", "heya") as log:
            warnings.warn("heya")  # warning will be captured
            warnings.warn("yow")   # warning will not be captured
        assert len(log) == 1  # log is a list of filtered warnings


        @filter_warnings("default", "heya")
        def func(arg):
            warnings.warn("heya")  # warning will be captured
            warnings.warn("yow")   # warning will not be captured


        @filter_warnings("default", "heya")
        class TestSomething(TestCase):
            def test_thing():
                warnings.warn("heya")  # warning will be captured
                warnings.warn("yow")   # warning will not be captured
    ```
    """

    @unit_testing_only
    def __init__(self, action, message="", category=Warning, module="", lineno=0, append=False):
        self.filter = (action, message, category, module, lineno, append)

    def __repr__(self):
        return f"{type(self).__name__}{self.filter}"

    def __enter__(self):
        """Start filtering warnings

        Returns a list that will be populated with captured warnings.
        """
        if not hasattr(self, "context"):
            self.context = warnings.catch_warnings(record=True)
        log = self.context.__enter__()
        warnings.filterwarnings(*self.filter)
        return log

    def __exit__(self, *exc_info):
        """Stop filtering warnings."""
        self.context.__exit__(*exc_info)
        del self.context
