from datetime import datetime
from django.http import HttpRequest, HttpResponseBadRequest
from django.utils.formats import get_format
from dimagi.utils.dates import DateSpan

def datespan_in_request(from_param="from", to_param="to", default_days=30):
    """
    Wraps a request with dates based on url params or defaults and
    Checks date validity.
    """
    
    # this is loosely modeled after example number 4 of decorator
    # usage here: http://www.python.org/dev/peps/pep-0318/
    def get_dates(f):
        def wrapped_func(*args, **kwargs):
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
                date_input_formats = get_format('DATE_INPUT_FORMATS')
                default_format = date_input_formats[0]
                def date_or_nothing(param):
                    if param not in dict or not dict[param]:
                        return None, None
                    for format in date_input_formats:
                        try:
                            return datetime.strptime(dict[param], format), format
                        except ValueError:
                            continue
                    raise ValueError('Improperly formatted date. Please enter dates in the format %(format)s' % 
                                     {'format': default_format})
                try:             
                    startdate, start_format = date_or_nothing(from_param)
                    enddate, end_format = date_or_nothing(to_param)
                except ValueError, e:
                    return HttpResponseBadRequest(unicode(e))
                if startdate or enddate:
                    req.datespan = DateSpan(startdate, enddate, start_format)
                else:
                    # default to the last N days
                    req.datespan = DateSpan.since(default_days, format=default_format)
                    
            return f(*args, **kwargs) 
        if hasattr(f, "func_name"):
            wrapped_func.func_name = f.func_name
            # preserve doc strings
            wrapped_func.__doc__ = f.__doc__  
            
            return wrapped_func
        else:
            # this means it wasn't actually a view.  
            return f 
    return get_dates

def _is_http_request(obj):
    return obj and isinstance(obj, HttpRequest)
