from functools import wraps


def print_return_value(fn):
    @wraps(fn)
    def _inner(*args, **kwargs):
        return_value = fn(*args, **kwargs)
        print return_value
        return return_value
    return _inner
