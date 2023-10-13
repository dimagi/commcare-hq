from couchdbkit.exceptions import ResourceConflict
from django.utils.functional import wraps
from six.moves import range


class RetryResourceError(Exception):
    def __init__(self, fn, attempts):
        self.fn = fn
        self.attempts = attempts

    def __str__(self):
        return repr(
            f"Tried function `{self.fn.__name__}` {self.attempts} time(s) and "
            "conflicted every time."
        )


def retry_resource(n):
    def decorator(fn):
        @wraps(fn)
        def new_fn(*args, **kwargs):
            for _ in range(n):
                try:
                    return fn(*args, **kwargs)
                except ResourceConflict:
                    pass
            raise RetryResourceError(fn, n)
        return new_fn
    return decorator
