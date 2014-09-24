from __future__ import absolute_import
from decimal import Decimal
import datetime
import iso8601
from jsonobject import JsonProperty, DateTimeProperty
from jsonobject.exceptions import BadValueError
from collections import namedtuple


def _canonical_decimal(n):
    """
    raises ValueError for non-canonically formatted decimal strings

    example: '00.1' or '.1' whose canonical form is '0.1'

    """
    decimal = Decimal(n)
    if unicode(decimal) != n:
        raise ValueError('{!r} is not a canonically formatted decimal')
    return decimal


GeoPoint = namedtuple('GeoPoint', 'latitude longitude altitude accuracy')


class GeoPointProperty(JsonProperty):
    """
    wraps a GeoPoint object where the numbers are represented as Decimals
    to preserve exact formatting (number of decimal places, etc.)

    """

    def wrap(self, obj):
        try:
            return GeoPoint(*[_canonical_decimal(n) for n in obj.split(' ')])
        except (ValueError, TypeError):
            raise BadValueError("{!r} is not a valid format GeoPoint format"
                                .format(obj))

    def unwrap(self, obj):
        return obj, '{} {} {} {}'.format(*obj)


class ISO8601Property(DateTimeProperty):
    """
    >>> ISO8601Property().wrap('2014-12-11T01:05:18+03:00')
    datetime.datetime(2014, 12, 10, 22, 5, 18)
    >>> ISO8601Property().unwrap(_)
    (datetime.datetime(2014, 12, 10, 22, 5, 18), '2014-12-10T22:05:18.000000Z')

    """
    def __init__(self, **kwargs):
        if 'exact' in kwargs:
            assert kwargs['exact'] is True
        kwargs['exact'] = True
        super(ISO8601Property, self).__init__(**kwargs)

    def wrap(self, obj):
        dt = iso8601.parse_date(obj)
        return dt.astimezone(iso8601.iso8601.UTC).replace(tzinfo=None)


class ISOMeta(object):
    update_properties = {datetime.datetime: ISO8601Property}
