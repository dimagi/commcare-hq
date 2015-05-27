from functools import wraps
from django.conf import settings


def unit_testing_only(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        assert settings.UNIT_TESTING, \
            'You may only call {} during unit testing'.format(fn.__name__)
        return fn(*args, **kwargs)
    return inner
