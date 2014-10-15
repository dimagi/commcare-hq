from __future__ import absolute_import
from decimal import Decimal
import datetime
import iso8601
from jsonobject import JsonProperty, DateTimeProperty, JsonObject
from jsonobject.exceptions import BadValueError
from collections import namedtuple
import re
from corehq.ext.datetime import UTCDateTime


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


class UTCDateTimeProperty(DateTimeProperty):
    """
    `UTCDateTimeProperty` uses `UTCDateTime`s exclusively

    It reads in any ISO 8601 datetime,
    but strictly writes out ISO 8601 unicode datetimes,
    with microseconds (and the 'Z' ending),
    followed by a space and the UTC offset string (e.g. '-04:00').

    """
    UTC_DATE_TIME_RE = re.compile(
        r'^'
        r'\d\d\d\d-(0[1-9]|1[0-2])-([12]\d|0[1-9]|3[01])T'
        r'([01]\d|2[0-3]):([0-5]\d):([0-5]\d).\d\d\d\d\d\dZ '
        # encode the UTCDateTime's timezone rules: no more than +/-14 hours
        # minutes in increments of 15
        r'[\+-](0\d|1[0-4]):(00|15|30|45)'
        r'$'
    )

    def __init__(self, **kwargs):
        if 'exact' in kwargs:
            assert kwargs['exact'] is True
        kwargs['exact'] = True
        super(UTCDateTimeProperty, self).__init__(**kwargs)

    def _wrap(self, value):
        if self.UTC_DATE_TIME_RE.match(value):
            dt_string, tz_string = value.split(' ')
            dt = iso8601.parse_date(dt_string)
            assert dt.utcoffset() == datetime.timedelta(0)
            return UTCDateTime.from_datetime(dt.replace(tzinfo=None),
                                             original_offset=tz_string)
        else:
            dt = iso8601.parse_date(value)
            if dt.utcoffset() == datetime.timedelta(0):
                # UTC might have been inferred
                # if not explicit, remove it
                if all(z not in value for z in ('z', 'Z', '+00:00', '-00:00')):
                    dt = dt.replace(tzinfo=None)
            return UTCDateTime.from_datetime(dt)

    def _unwrap(self, value):
        utc_dt = UTCDateTime.from_datetime(value)
        _, unwrapped = super(UTCDateTimeProperty, self)._unwrap(utc_dt)
        if utc_dt.tz_string:
            return utc_dt, '{} {}'.format(unwrapped, utc_dt.tz_string)
        else:
            # for naive datetimes, strip final Z
            assert unwrapped[-1] == 'Z'
            return utc_dt, unwrapped[:-1]


class ISOMeta(object):
    update_properties = {
        datetime.datetime: UTCDateTimeProperty,
        UTCDateTime: UTCDateTimeProperty,
    }

    string_conversions = JsonObject.Meta.string_conversions + (
        (UTCDateTimeProperty.UTC_DATE_TIME_RE, datetime.datetime),
    )
