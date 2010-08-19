from __future__ import absolute_import
from django.http import HttpRequest

from requestlogger.models import RequestLog

import logging

def log_request():
    """Decorator for views that logs information about the 
       request before passing it to the view."""
    # this is loosely modeled after example number 4 of decorator
    # usage here: http://www.python.org/dev/peps/pep-0318/
    def log_and_call(f):
        def wrapped_func(*args, **kwargs):
            # wrap everything besides the function call in a try/except
            # block.  we don't ever want the logging to prevent the 
            # basic view functionality from working. 
            try:
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
                    log = RequestLog.from_request(arg)
                    log.save()
                else: 
                    logging.error("No request argument found for %s, information will not be logged." %
                                   f.func_name)
            except Exception, e:
                logging.error("Error logging request!  The error is: %s." % e)
            return f(*args, **kwargs) 
        if hasattr(f, "func_name"):
            wrapped_func.func_name = f.func_name
            return wrapped_func
        else:
            # this means it wasn't actually a view.  I think we
            # want to default to not wrapping or logging it here.
            logging.error("%s is not a function.  Request will not be logged" % f)
            return f 
    return log_and_call

def _is_http_request(obj):
    return obj and isinstance(obj, HttpRequest)