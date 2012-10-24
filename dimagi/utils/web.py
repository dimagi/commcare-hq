#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from __future__ import absolute_import
import os, re, traceback, sys
from django.conf import settings
from django.http import HttpResponse
from django.template import RequestContext
from django.shortcuts import render_to_response as django_r_to_r
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.contrib.sites.models import Site
import json
from dimagi.utils.parsing import json_format_datetime
from datetime import date, datetime
from decimal import Decimal

def get_url_base():
    try:
        protocol = settings.DEFAULT_PROTOCOL
    except:
        protocol = 'http'
    return '%s://%s' % (protocol, Site.objects.get(id = settings.SITE_ID).domain)

def get_secure_url_base():
    return 'https://%s' % Site.objects.get(id = settings.SITE_ID).domain

def render_to_response(req, template_name, dictionary=None, **kwargs):
    """Proxies calls to django.shortcuts.render_to_response, to avoid having
       to include the global variables in every request. This is a giant hack,
       and there's probably a much better solution."""

    def _tab_order_sorter(app1, app2):
        """Sort apps, based on the tab_order property in the config, if it exists.
           Anything with a value specified comes before everything else, which
           is arbitrarily sorted at the end."""
        app1_order = int(app1["taborder"]) if "taborder" in app1 else sys.maxint
        app2_order = int(app2["taborder"]) if "taborder" in app2 else sys.maxint
        return app1_order - app2_order

    rs_dict = {
        "apps":  sorted(settings.INSTALLED_APPS, _tab_order_sorter),
        "debug": settings.DEBUG,
    }

    # A NEW KIND OF LUNACY: inspect the stack to find out
    # which app this function is being called from
    tb = traceback.extract_stack(limit=2)
    sep = os.sep
    if sep == '\\':
        # if windows, the file separator itself needs to be
        # escaped again
        sep = "\\\\"
    m = re.match(r'^.+%s(.+?)%sviews\.py$' % (sep, sep), tb[-2][0])
    if m is not None:
        app_type = m.group(1)

        # note which app this func was called from, so the tmpl
        # can mark the tab (or some other type of nav) as active
        rs_dict["active_tab"] = app_type

    # allow the dict argument to
    # be omitted without blowing up
    if dictionary is not None:
        rs_dict.update(dictionary)

    # unless a context instance has been provided,
    # default to RequestContext, to get all of
    # the TEMPLATE_CONTEXT_PROCESSORS working
    if "context_instance" not in kwargs:
        kwargs["context_instance"] = RequestContext(req)

    # pass on the combined dicts to the original function
    return django_r_to_r(template_name, rs_dict, **kwargs)


def paginated(req, query_set, per_page=20, prefix="", wrapper=None):

    # since the behavior of this function depends on
    # the GET parameters, if there is more than one
    # paginated set per view, we'll need to prefix
    # the parameters to differentiate them
    prefix = ("%s-" % (prefix)) if prefix else ""

    # the per_page argument to this function provides
    # a default, but can be overridden per-request. no
    # interface for this yet, so it's... an easter egg?
    if (prefix + "per-page") in req.GET:
        try:
            per_page = int(req.GET[prefix+"per-page"])

        # if it was provided, it must be valid. we don't
        # want links containing extra useless junk like
        # invalid GET parameters floating around
        except ValueError:
            raise ValueError("Invalid per-page parameter: %r" %
                (req.GET[prefix + "per-page"]))

    try:
        page = int(req.GET.get(prefix+"page", "1"))
        paginator = Paginator(query_set, per_page)
        objects = paginator.page(page)

    # have no mercy if the page parameter is not valid. there
    # should be no links to an invalid page, so coercing it to
    # assume "page=xyz" means "page=1" would just mask bugs
    except (ValueError, EmptyPage, InvalidPage):
        raise ValueError("Invalid Page: %r" %
            (req.GET[prefix + "page"]))

    # if a wrapper function was provided, call it for each
    # object on the page, and replace the list with the result
    if wrapper is not None:
        objects.raw_object_list = objects.object_list
        objects.object_list = map(wrapper, objects.object_list)

    # attach the prefix (if provided; might be blank) to the
    # objects, where it can be found by the {% paginator %} tag
    objects.prefix = prefix

    return objects


def self_link(req, **kwargs):
    new_kwargs = req.GET.copy()

    # build a new querydict using the GET params from the
    # current request, with those passed to this function
    # overridden. we can't use QueryDict.update here, since
    # it APPENDS, rather than REPLACING keys. i hate CGI :|
    for k, v in kwargs.items():
        new_kwargs[k] = v

    # return the same path that we're currently
    # viewing, with the updated query string
    kwargs_enc = new_kwargs.urlencode()
    return "%s?%s" % (req.path, kwargs_enc)

def web_message(req, msg, link=None):
    return render_to_response(req,
        "message.html", {
            "message": msg,
            "link": link
    })

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
    elif isinstance(obj, Decimal):
        return float(obj) # warning, potential loss of precision
    else:
        return json.JSONEncoder().default(obj)

def json_response(obj, **kwargs):
    if not kwargs.has_key('default'):
        kwargs['default'] = json_handler
    return HttpResponse(json.dumps(obj, **kwargs), mimetype="application/json")

def json_request(params, lenient=True):
    d = {}
    for key, val in params.items():
        try:
            d[str(key)] = json.loads(val)
        except ValueError:
            if lenient:
                d[str(key)] = val
            else:
                raise
    return d


# get_ip was stolen verbatim from auditcare.utils
# this is not intended to be an all-knowing IP address regex
IP_RE = re.compile('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')

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
    ip_address = request.META.get('HTTP_X_FORWARDED_FOR',
        request.META.get('REMOTE_ADDR', '127.0.0.1'))
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
