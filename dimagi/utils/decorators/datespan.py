from datetime import datetime
from django.http import HttpRequest, HttpResponseBadRequest
from dimagi.utils.dates import DateSpan
from dimagi.utils.django.request import request_from_args_or_kwargs

def datespan_in_request(from_param="from", to_param="to", 
                        format_string="%Y-%m-%d", default_days=30, 
                        inclusive=True, default_function=None):
    """
    Wraps a request with dates based on url params or defaults and
    Checks date validity.
    """
    # you can pass in a function to say what the default should be, 
    # if you don't it will pull the value from the last default_days
    # in. If you override default_function, default_days is ignored.
    if default_function is None:
        default_function = lambda: DateSpan.since(default_days, 
                                                  format=format_string, 
                                                  inclusive=inclusive)
    
    # this is loosely modeled after example number 4 of decorator
    # usage here: http://www.python.org/dev/peps/pep-0318/
    def get_dates(f):
        def wrapped_func(*args, **kwargs):
            # attempt to find the request object from all the argument
            # values, checking first the args and then the kwargs
            req = request_from_args_or_kwargs(*args, **kwargs)
            if req:
                dict = req.POST if req.method == "POST" else req.GET
                def date_or_nothing(param):
                    return datetime.strptime(dict[param], format_string)\
                             if param in dict and dict[param] else None
                try:             
                    startdate = date_or_nothing(from_param)
                    enddate = date_or_nothing(to_param)
                except ValueError, e:
                    return HttpResponseBadRequest(unicode(e))
                if startdate or enddate:
                    req.datespan = DateSpan(startdate, enddate, format_string)
                else:        
                    req.datespan = default_function()
                    req.datespan.is_default = True
                    
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
