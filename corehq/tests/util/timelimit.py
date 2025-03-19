from functools import wraps
from inspect import isgeneratorfunction
from time import time

_context = []


def timelimit(limit):
    """Create a decorator that asserts a run time limit

    An assertion error is raised if the decorated function returns
    without raising an error and the elapsed run time is longer than
    the allowed time limit.

    Can be used to override the limit imposed by --max-test-time.
    Note: this decorator is not thread-safe.

    Usage:

        @timelimit
        def lt_one_second():
            ...

        @timelimit(0.5)
        def lt_half_second():
            ...

    :param limit: number of seconds or a callable to decorate. If
    callable, the time limit defaults to one second.
    """
    # Import here to avoid breaking the docs build on github actions.
    # Error: Handler <function setup_django> for event 'config-inited'
    # threw an exception (exception: No module named 'pytest')
    from ..pytest_plugins.timelimit import increase_max_test_time

    if callable(limit):
        return timelimit((limit, 1))
    if not isinstance(limit, tuple):
        return lambda func: timelimit((func, limit))
    func, seconds = limit

    if isgeneratorfunction(func):
        raise ValueError(f"cannot use 'timelimit' on generator function: {func}")

    @wraps(func)
    def time_limit(*args, **kw):
        level = len(_context)
        try:
            _context.append(seconds)
            increase_max_test_time(seconds)
            start = time()
            rval = func(*args, **kw)
            elapsed = time() - start
            limit = sum(_context[level:])
        finally:
            if level == 0:
                _context.clear()
        assert elapsed < limit, f"{func.__name__} time limit ({limit}) exceeded: {elapsed}"
        return rval
    time_limit.max_test_time = seconds
    return time_limit
