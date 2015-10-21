from dateutil.parser import parse
from dimagi.ext.couchdbkit import DateTimeProperty, Property
import json

def parse_date_string(datestring, precise=False):
    """
    >>> parse_date_string('2013-01-03T11:27:06.045000Z')
    datetime.datetime(2013, 1, 3, 11, 27, 6)
    >>> parse_date_string('2013-01-03T11:27:06.045000Z', True)
    datetime.datetime(2013, 1, 3, 11, 27, 6, 45000)
    >>> parse_date_string('2013-01-03T11:27:06Z', True)
    datetime.datetime(2013, 1, 3, 11, 27, 6)
    >>> parse_date_string('2013-01-03T11:27:06', True)
    datetime.datetime(2013, 1, 3, 11, 27, 6)
    >>> parse_date_string('2013-01-03T11:27:06+03:00', True)
    datetime.datetime(2013, 1, 3, 11, 27, 6)
    """
    date_with_tz = parse(datestring)
    if not precise:
        date_with_tz = date_with_tz.replace(microsecond=0)
    # couchdbkit throws away timezones too so while this may not be technically
    # correct, at least it's consistent
    return date_with_tz.replace(tzinfo=None)

class TimeStampProperty(DateTimeProperty):
    """
    A more precise version of the DateTime property.

    Configurably provide the data back out in both precise or non-precise
    modes. Useful if you want to do comparisons with normal DateTimeProperties
    but still want to store the extra precision for potential future need.
    """
    def __init__(self, precise_reads=False, **kwargs):
        self.precise_reads = precise_reads
        super(TimeStampProperty, self).__init__(**kwargs)

    def to_python(self, value):
        if isinstance(value, basestring):
            try:
                return parse_date_string(value, self.precise_reads)
            except ValueError, e:
                raise ValueError('Invalid ISO date/time %r [%s]' %
                        (value, str(e)))
        return value

    def to_json(self, value):
        if value is None:
            return value
        return value.isoformat() + 'Z'

class JsonProperty(Property):
    """
    A property that stores data in an arbitrary JSON object.
    """

    def to_python(self, value):
        return json.loads(value)

    def to_json(self, value):
        return json.dumps(value)

