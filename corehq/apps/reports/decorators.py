from __future__ import absolute_import
from datetime import datetime, timedelta
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