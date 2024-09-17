from datetime import datetime, timedelta
from functools import wraps


def timelimit(limit):
    """Create a decorator that asserts a run time limit

    An assertion error is raised if the decorated function returns
    without raising an error and the elapsed run time is longer than
    the allowed time limit.

    This decorator can be used to extend the time limit imposed by
    --max-test-time when `corehq.tests.noseplugins.timing.TimingPlugin`
    is enabled.

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
    if callable(limit):
        return timelimit((limit, timedelta(seconds=1)))
    if not isinstance(limit, tuple):
        limit = timedelta(seconds=limit)
        return lambda func: timelimit((func, limit))
    func, limit = limit

    @wraps(func)
    def time_limit(*args, **kw):
        # TODO restore when timing nose plugin is adapted to pytest
        #from corehq.tests.noseplugins.timing import add_time_limit
        #add_time_limit(limit.total_seconds())
        start = datetime.utcnow()
        rval = func(*args, **kw)
        elapsed = datetime.utcnow() - start
        assert elapsed < limit, f"{func.__name__} took too long: {elapsed}"
        return rval
    return time_limit
