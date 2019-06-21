from __future__ import absolute_import

from contextlib import contextmanager

from django.http import HttpRequest


def _is_http_request(obj):
    return obj and isinstance(obj, HttpRequest)


def request_from_args_or_kwargs(*args, **kwargs):
    req = None
    for arg in args:
        if _is_http_request(arg):
            req = arg
            break
    if not req:
        for arg in kwargs.values():
            if _is_http_request(arg):
                req = arg
                break
    return req


@contextmanager
def mutable_querydict(query_dict):
    query_dict._mutable = True
    try:
        yield query_dict
    finally:
        query_dict._mutable = False
