import functools
from elasticsearch import exceptions as elasticsearch_exceptions
from requests import exceptions as requests_exceptions


def require_elasticsearch(fn):
    @functools.wraps(fn)
    def decorated(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (requests_exceptions.ConnectionError, elasticsearch_exceptions.ConnectionError):
            pass
    return decorated
