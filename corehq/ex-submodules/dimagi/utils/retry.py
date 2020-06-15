from functools import wraps
from itertools import chain
from time import sleep


def retry_on(
    *errors,
    should_retry=lambda err: True,
    delays=(0.1, 1, 2, 4, 8),
):
    """Make a decorator to retry function on any of the given errors

    Retry up to 5 times with exponential backoff. Raise the last
    received error if all calls fail.

    :param *errors: One or more errors (exception classes) to catch and retry.
    :param should_retry: Optional function taking one argument, an
        exception instance, that returns true to signal a retry and false
        to signal that the error should be re-raised.
    :param delays: A list of delays given in seconds.
    :returns: a decorator to be applied to functions that should be
        retried if they raise one of the given errors.
    """
    errors = tuple(errors)

    def retry_decorator(func):
        @wraps(func)
        def retry(*args, **kw):
            for delay in chain(delays, [None]):
                try:
                    return func(*args, **kw)
                except errors as err:
                    if delay is None or not should_retry(err):
                        raise
                    sleep(delay)
        return retry
    return retry_decorator
