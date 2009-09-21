from __future__ import absolute_import
from django.http import HttpRequest

from requestlogger.models import RequestLog

def log_request():
    """
    Decorator for views that logs information about the 
    request before passing it to the view.
    """
    def log_and_call(f):
        def wrapped_func(*args, **kwargs):
            # attempt to find the request object from all the values
            req = None
            for arg in args:
                if _is_http_request(arg):
                    req = arg
                    break
            if not req:
                # check kwargs if we didn't find it in args
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
            return f(*args, **kwargs) 
        wrapped_func.func_name = f.func_name
        return wrapped_func
    return log_and_call

def _is_http_request(obj):
    return isinstance(obj, HttpRequest)