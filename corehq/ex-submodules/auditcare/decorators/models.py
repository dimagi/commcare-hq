from copy import deepcopy
from functools import wraps


def store_original_doc():
    def decorator(fn):
        @wraps(fn)
        def _inner(self, *args, **kwargs):
            model_object = fn(self, *args, **kwargs)
            model_object._original = deepcopy(model_object._doc)
            return model_object
        return _inner
    return decorator
