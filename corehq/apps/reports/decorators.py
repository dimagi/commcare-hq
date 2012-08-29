from __future__ import absolute_import
from datetime import datetime, timedelta
from django.core.cache import cache
from django.http import HttpRequest

import logging
from dimagi.utils.parsing import string_to_datetime

def wrap_with_dates():
    """Wraps a request with dates based on url params or defaults and
       Checks date validity."""
    # this is loosely modeled after example number 4 of decorator
    # usage here: http://www.python.org/dev/peps/pep-0318/
    def get_dates(f):
        def wrapped_func(*args, **kwargs):
            # wrap everything besides the function call in a try/except
            # block.  we don't ever want this to prevent the 
            # basic view functionality from working. 
            # attempt to find the request object from all the argument
            # values, checking first the args and then the kwargs 
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
            if req:
                dict = req.POST if req.method == "POST" else req.GET
                req.startdate = None
                req.enddate = None
                if "startdate" in dict:
                    if "enddate" in dict:
                        req.startdate = string_to_datetime(dict["startdate"])
                        req.enddate = string_to_datetime(dict["enddate"])
                        if req.enddate < req.startdate:
                            raise Exception(("You can't have an end date "
                                             "of %s after start date of %s")
                                             % (req.enddate, req.startdate))
                    else:
                        # TODO: Be more graceful
                        raise Exception("You have to specify both or 0 dates!")
                else:
                    # default to the current month
                    now = datetime.now()
                    first_of_next_month = datetime(now.year, now.month + 1, 1)
                    req.enddate = first_of_next_month - timedelta(days=1)
                    req.startdate = datetime(now.year, now.month, 1)
                    
            return f(*args, **kwargs) 
        if hasattr(f, "func_name"):
            wrapped_func.func_name = f.func_name
            return wrapped_func
        else:
            # this means it wasn't actually a view.  
            return f 
    return get_dates

def _is_http_request(obj):
    return obj and isinstance(obj, HttpRequest)

def _validate_timeouts(refresh_stale, cache_timeout):
    if not isinstance(cache_timeout, int):
        raise ValueError('Cache timeout should be an int. '
                         'It is the number of seconds until the cache expires.')
    if not isinstance(refresh_stale, int):
        raise ValueError('refresh_stale should be an int. '
                         'It is the number of seconds to wait until celery regenerates the cache.')

def cache_report(refresh_stale=1800, cache_timeout=3600):
    _validate_timeouts(refresh_stale, cache_timeout)
    def cacher(func):
        def retrieve_cache(report):
            from corehq.apps.reports.generic import GenericReportView
            if not isinstance(report, GenericReportView):
                raise ValueError("The decorator 'cache_report' is only for reports that are instances of GenericReportView.")
            if report._caching:
                return func(report)

            path = report.request.META.get('PATH_INFO')
            query = report.request.META.get('QUERY_STRING')
            cache_key = "%s:%s:%s:%s" % (report.__class__.__name__, func.__name__, path, query)

            cached_data = None
            try:
                cached_data = cache.get(cache_key)
            except Exception as e:
                logging.error("Could not fetch cache for report %s due to error: %s" % (report.name, e))

            if isinstance(cached_data, dict):
                context = cached_data.get('data', dict())
            else:
                context = func(report)

            try:
                from corehq.apps.reports.tasks import report_cacher
                report_cacher.delay(report, func.__name__, cache_key,
                    current_cache=cached_data, refresh_stale=refresh_stale, cache_timeout=cache_timeout)
            except Exception as e:
                logging.error("Could not send <%s, %s> to report_cacher due to error: %s" %
                              (report.__class__.__name__, func.__name__, e))

            return context
        return retrieve_cache
    return cacher

def cache_users(refresh_stale=1800, cache_timeout=3600):
    _validate_timeouts(refresh_stale, cache_timeout)
    def cacher(func):
        def retrieve_cache(domain, **kwargs):
            caching = kwargs.get('caching', False)
            simplified = kwargs.get('simplified', False)
            if caching or not simplified:
                return func(domain, **kwargs)

            individual = kwargs.get('individual')
            group = kwargs.get('group')
            user_filter = kwargs.get('user_filter')

            cache_key = "%(domain)s:USERS:%(group)s:%(individual)s:%(filters)s" % dict(
                domain=domain,
                group=group,
                individual=individual,
                filters=".".join(["%s" % f.type for f in user_filter])
            )

            cached_data = None
            try:
                cached_data = cache.get(cache_key)
            except Exception as e:
                logging.error('Could not fetch cached users list for domain %s due to error: %s' % (domain, e))

            if isinstance(cached_data, dict):
                user_list = cached_data.get('data', [])
            else:
                user_list = func(domain, **kwargs)

            try:
                from corehq.apps.reports.tasks import user_cacher
                user_cacher.delay(domain, cache_key, cached_data, refresh_stale, cache_timeout, caching=True, **kwargs)
            except Exception as e:
                logging.error("Could not send user list for domain %s to user_cacher due to error: %s" % (domain, e))

            return user_list
        return retrieve_cache
    return cacher