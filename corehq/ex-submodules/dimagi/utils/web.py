#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

import os
import re
import traceback
import sys
import warnings

from django.conf import settings
from django.http import HttpResponse
import json
from django.utils.encoding import force_text
from django.utils.functional import Promise
from dimagi.utils.parsing import json_format_datetime
from datetime import date, datetime, time
from decimal import Decimal


def get_url_base():
    return '{}://{}'.format(settings.DEFAULT_PROTOCOL, get_site_domain())


def get_site_domain():
    return settings.BASE_ADDRESS


def get_static_url_prefix():
    return '' if settings.STATIC_CDN else 'http://' + get_site_domain()


def parse_int(arg_keys=[], kwarg_keys=[]):
    """
    A decorator to translate coerce arguments to be ints

    >>> @parse_int([0,1])
    >>> def add(x,y):
    ...     return x + y
    ...
    >>> add("1", "2")
    3

    """
    def _parse_int(fn):
        def _fn(*args, **kwargs):
            args = list(args)
            kwargs = dict(kwargs)
            for i in arg_keys:
                args[i] = int(args[i])
            for key in kwarg_keys:
                kwargs[key] = int(kwargs[key])
            return fn(*args, **kwargs)
        return _fn
    return _parse_int


# http://stackoverflow.com/questions/455580/json-datetime-between-python-and-javascript
def json_handler(obj):
    if callable(getattr(obj, 'to_complete_json', None)):
        return obj.to_complete_json()
    elif callable(getattr(obj, 'to_json', None)):
        return obj.to_json()
    elif isinstance(obj, datetime):
        return json_format_datetime(obj)
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, time):
        return obj.strftime('%H:%M:%S')
    elif isinstance(obj, Decimal):
        return float(obj) # warning, potential loss of precision
    elif isinstance(obj, Promise):
        return force_text(obj)  # to support ugettext_lazy
    elif isinstance(obj, bytes):
        return obj.decode('utf-8')
    else:
        return json.JSONEncoder().default(obj)


def json_response(obj, status_code=200, **kwargs):
    warnings.warn(
        "json_response is deprecated.  Use django.http.JsonResponse instead.",
        DeprecationWarning,
    )
    if 'default' not in kwargs:
        kwargs['default'] = json_handler
    return HttpResponse(json.dumps(obj, **kwargs), status=status_code,
                        content_type="application/json")


def json_request(params, lenient=True, booleans_as_strings=False):
    d = {}
    for key, val in params.items():
        try:
            if booleans_as_strings and val in ('true', 'false'):
                d[str(key)] = val
            else:
                d[str(key)] = json.loads(val)
        except ValueError:
            if lenient:
                d[str(key)] = val
            else:
                raise
    return d


# this is not intended to be an all-knowing IP address regex
IP_RE = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')


def get_ip(request):
    """
    Retrieves the remote IP address from the request data.  If the user is
    behind a proxy, they may have a comma-separated list of IP addresses, so
    we need to account for that.  In such a case, only the first IP in the
    list will be retrieved.  Also, some hosts that use a proxy will put the
    REMOTE_ADDR into HTTP_X_FORWARDED_FOR.  This will handle pulling back the
    IP from the proper place.
    """

    # if neither header contain a value, just use local loopback
    ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '127.0.0.1'))
    if ip_address:
        # make sure we have one and only one IP
        try:
            ip_address = IP_RE.match(ip_address)
            if ip_address:
                ip_address = ip_address.group(0)
            else:
                # no IP, probably from some dirty proxy or other device
                # throw in some bogus IP
                ip_address = '10.0.0.1'
        except IndexError:
            pass
    return ip_address
