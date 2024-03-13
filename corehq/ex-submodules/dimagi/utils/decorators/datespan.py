from datetime import datetime
from dimagi.utils.dates import DateSpan
from dimagi.utils.django.request import request_from_args_or_kwargs
from dimagi.utils.parsing import ISO_DATE_FORMAT


def datespan_in_request(from_param="from", to_param="to",
                        format_string=ISO_DATE_FORMAT, default_days=30,
                        inclusive=True, default_function=None):
    """
    Wraps a request with dates based on url params or defaults and
    Checks date validity.
    """
    # you can pass in a function to say what the default should be,
    # if you don't it will pull the value from the last default_days
    # in. If you override default_function, default_days is ignored.
    if default_function is None:
        def default_function():
            return DateSpan.since(default_days, format=format_string, inclusive=inclusive)

    # this is loosely modeled after example number 4 of decorator
    # usage here: http://www.python.org/dev/peps/pep-0318/
    def get_dates(f):
        def wrapped_func(*args, **kwargs):
            # attempt to find the request object from all the argument
            # values, checking first the args and then the kwargs
            req = request_from_args_or_kwargs(*args, **kwargs)
            if req:
                req_dict = req.POST if req.method == "POST" else req.GET
                def date_or_nothing(param):
                    date = req_dict.get(param, None)
                    try:
                        return datetime.strptime(date, format_string) if date else None
                    except ValueError:
                        return None
                startdate = date_or_nothing(from_param)
                enddate = date_or_nothing(to_param)
                if startdate or enddate:
                    req.datespan = DateSpan(startdate, enddate, format_string)
                else:
                    req.datespan = default_function()
                    req.datespan.is_default = True

            return f(*args, **kwargs)

        if hasattr(f, "__name__"):
            wrapped_func.__name__ = f.__name__
            # preserve doc strings
            wrapped_func.__doc__ = f.__doc__
            return wrapped_func
        else:
            # this means it wasn't actually a view.
            return f
    return get_dates
