from couchdbkit.exceptions import ResourceConflict
from django.utils.functional import wraps

def repeat(fn, n):
    for _ in range(n):
        try:
            return fn()
        except ResourceConflict:
            pass


def retry_resource(n):
    def decorator(fn):
        @wraps(fn)
        def new_fn(*args, **kwargs):
            for _ in range(n):
                try:
                    return fn(*args, **kwargs)
                except ResourceConflict:
                    pass
        return new_fn
    return decorator