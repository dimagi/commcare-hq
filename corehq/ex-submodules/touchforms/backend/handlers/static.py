from customhandlers import TouchformsFunctionHandler
from java.text import SimpleDateFormat
from java.util import TimeZone

class StaticFunctionHandler(TouchformsFunctionHandler):
    """
    A function handler that lets you register a static value associated with a function.

    In order to use add the following section to your form context:

    "static": [
        {"name": "foo_func", "value": "foo"},
        {"name": "bar_func", "value": "bar"}
    ]

    This Will add two static context handlers to the session with the following xpath mappings

        foo_func() --> "foo"
        bar_func() --> "bar"

    """

    @classmethod
    def slug(self):
        return 'static'

    def __init__(self, name, value):
        self._name = name
        self._value = value

    def getName(self):
        return self._name

    def eval(self, args, ec):
        return self._value


class StaticDateFunctionHandler(StaticFunctionHandler):
    """
    A function handler that works just like the StaticFunctionHandler except it parses
    the passed in value to a java.util.Date object.

    Accepts strings in the following ISO-8601 formats:

    - Dates: 2015-07-01
    - Datetimes (UTC): 2015-07-01T14:52:58Z
    - Datetimes with microseconds (UTC): 2015-07-01T14:52:58.473000Z

    Fails hard if not passed a valid non-empty string in one of these formats
    """

    @classmethod
    def slug(self):
        return 'static-date'

    def __init__(self, name, value):
        self._name = name
        if not value:
            self._value = value
        else:
            if len(value) == 10:
                # date format
                parsed_value = SimpleDateFormat('yyyy-MM-dd').parse(value)
            else:
                # assume datetime format
                # remove microseconds if necessary
                if len(value) == 27:
                    value = '%sZ' % value[:19]
                sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'")
                sdf.setTimeZone(TimeZone.getTimeZone("UTC"))
                parsed_value = sdf.parse(value)
            self._value = parsed_value
