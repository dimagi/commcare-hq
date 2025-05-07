"""warnings test utilities"""
import warnings

from corehq.util.test_utils import unit_testing_only

from .context import testcontextmanager


class filter_warnings:
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

    def __call__(self, func=None):
        @testcontextmanager(before_class=True)
        def filter_context():
            with warnings.catch_warnings(record=True) as log:
                warnings.filterwarnings(*self.filter)
                yield log
        return filter_context(func)

    def __enter__(self):
        """Start filtering warnings

        Returns a list that will be populated with captured warnings.
        """
        assert not hasattr(self, "context")
        self.context = self()
        return self.context.__enter__()

    def __exit__(self, *exc_info):
        """Stop filtering warnings."""
        self.context.__exit__(*exc_info)
        del self.context
