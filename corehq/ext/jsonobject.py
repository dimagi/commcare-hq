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


class UTCDateTime(datetime.datetime):

    __ATTRS = ('year', 'month', 'day', 'hour', 'minute', 'second',
               'microsecond', 'original_offset')

    def __new__(cls, year, month, day, hour=0, minute=0, second=0,
                microsecond=0, original_offset=datetime.timedelta(0)):

        self = super(UTCDateTime, cls).__new__(cls, year, month, day, hour,
                                               minute, second, microsecond)
        assert isinstance(original_offset, datetime.timedelta)
        self.__original_offset = original_offset
        return self

    @property
    def original_offset(self):
        return self.__original_offset

    @classmethod
    def from_datetime(cls, dt):
        if isinstance(dt, UTCDateTime):
            return dt
        if dt.tzinfo is None:
            original_offset = datetime.timedelta(0)
            utc_dt = dt
        else:
            original_offset = dt.utcoffset()
            utc_dt = dt.astimezone(iso8601.iso8601.UTC).replace(tzinfo=None)
        self = cls(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour,
                   utc_dt.minute, utc_dt.second, utc_dt.microsecond,
                   original_offset=original_offset)
        return self

    @property
    def tz_string(self):
        return self.format_tz_string(self.__original_offset)

    @staticmethod
    def format_tz_string(offset):
        if offset is None:
            return ''
        seconds = offset.total_seconds()
        assert seconds - int(seconds) == 0
        seconds = int(seconds)
        if seconds < 0:
            sign = '-'
            seconds = -seconds
        else:
            sign = '+'
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        assert seconds == 0
        assert minutes in (0, 30)
        assert 0 <= hours < 15
        return '{}{:02d}:{:02d}'.format(sign, hours, minutes)

    def __eq__(self, other):
        for attr in self.__ATTRS:
            if getattr(self, attr) != getattr(other, attr):
                return False
        else:
            return True

    def __repr__(self):
        return u'{}({})'.format(
            self.__class__.__name__,
            u', '.join(repr(getattr(self, attr)) for attr in self.__ATTRS)
        )


class UTCDateTimeProperty(DateTimeProperty):
    def __init__(self, **kwargs):
        if 'exact' in kwargs:
            assert kwargs['exact'] is True
        kwargs['exact'] = True
        super(UTCDateTimeProperty, self).__init__(**kwargs)

    def _wrap(self, value):
        dt = iso8601.parse_date(value)
        return UTCDateTime.from_datetime(dt)

    def _unwrap(self, value):
        utc_dt = UTCDateTime.from_datetime(value)
        _, unwrapped = super(UTCDateTimeProperty, self)._unwrap(utc_dt)
        return utc_dt, '{} {}'.format(unwrapped, utc_dt.tz_string).rstrip()


class ISOMeta(object):
    update_properties = {datetime.datetime: UTCDateTimeProperty}
