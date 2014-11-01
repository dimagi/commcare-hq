from __future__ import absolute_import
import datetime
import pytz
import re


class UTCDateTime(datetime.datetime):
    """
    UTCDateTime acts like a tz-naive datetime
    but keeps track of an original_offset

    If you have a convention of using timezone-naive datetimes
    to implicitly mean UTC, then you can use UTCDateTimes to do so
    while still preserving original timezone information.

    Comparison between tz-aware datetimes and UTCDateTimes:

    >>> import pytz
    >>> # timezone-aware datetime
    >>> datetime.datetime(2014, 10, 8, 15, 30, 20, 239874,
    ...                   pytz.FixedOffset(-4 * 60))
    datetime.datetime(2014, 10, 8, 15, 30, 20, 239874, tzinfo=pytz.FixedOffset(-240))
    >>> # UTCDateTime
    >>> UTCDateTime.from_datetime(_)
    UTCDateTime(2014, 10, 8, 19, 30, 20, 239874, original_offset='-04:00')


    Notes that in the UTCDateTime example,
    the numbers for hours, minutes, etc. are in UTC time
    but the offset is preserved as original_offset,
    whereas in the timezone-aware datetime,
    the hours & minutes are localized to the timezone

    """

    __ATTRS = ('year', 'month', 'day', 'hour', 'minute', 'second',
               'microsecond', 'original_offset')
    __TZ_RE = re.compile(r'^([\+-])(\d\d):(\d\d)$')

    def __new__(cls, year, month, day, hour=0, minute=0, second=0,
                microsecond=0, original_offset=None):

        self = super(UTCDateTime, cls).__new__(cls, year, month, day, hour,
                                               minute, second, microsecond,
                                               tzinfo=None)
        if not isinstance(original_offset,
                          (type(None), datetime.timedelta, basestring)):
            raise TypeError('original_offset must be a timedelta or string')

        if isinstance(original_offset, basestring):
            # they passed in a '+hh:mm' formatted string as original_offset
            self.__original_offset = self.tz_string_to_offset(original_offset)
            self.__tz_string = original_offset
        else:
            self.__original_offset = original_offset
            self.__tz_string = self.tz_offset_to_string(original_offset)
        return self

    def __copy__(self):
        return UTCDateTime(**{attr: getattr(self, attr)
                              for attr in self.__ATTRS})

    def __deepcopy__(self, memo):
        return self.__copy__()

    @property
    def original_offset(self):
        return self.__original_offset

    @classmethod
    def from_datetime(cls, dt, original_offset=None):
        if original_offset is not None and (
                isinstance(dt, UTCDateTime) or dt.tzinfo is not None):
            raise ValueError('original_offset can only be specified '
                             'when it is not otherwise specified '
                             'by the datetime object itself')
        if isinstance(dt, UTCDateTime):
            return dt
        if dt.tzinfo is None:
            utc_dt = dt
        else:
            original_offset = dt.utcoffset()
            utc_dt = dt.astimezone(pytz.UTC).replace(tzinfo=None)
        self = cls(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour,
                   utc_dt.minute, utc_dt.second, utc_dt.microsecond,
                   original_offset=original_offset)
        return self

    def replace(self, **kwargs):
        unknown_kwargs = set(kwargs.keys()) - set(self.__ATTRS) - {'tzinfo'}
        if unknown_kwargs:
            raise TypeError(
                "'{}' is an invalid keyword argument for this function".format(
                    next(iter(unknown_kwargs)))
            )
        if 'tzinfo' in kwargs and 'original_offset' in kwargs:
            raise ValueError("only one of 'tzinfo' and 'original_offset' may "
                             "be passed as keyword arguments to this function")

        if 'tzinfo' in kwargs:
            return datetime.datetime(tzinfo=kwargs['tzinfo'], **{
                attr: kwargs[attr] if attr in kwargs else getattr(self, attr)
                for attr in self.__ATTRS if attr != 'original_offset'
            })
        else:
            return UTCDateTime(**{
                attr: kwargs[attr] if attr in kwargs else getattr(self, attr)
                for attr in self.__ATTRS
            })

    def to_datetime(self):
        """
        convert to a timezone-aware datetime

        """
        tz_naive_datetime = datetime.datetime(
            self.year, self.month, self.day,
            self.hour, self.minute, self.second,
            self.microsecond, tzinfo=None
        )
        if self.original_offset is not None:
            # this should have been checked at creation time
            assert self.original_offset.total_seconds() % 60 == 0
            return tz_naive_datetime.replace(tzinfo=pytz.UTC).astimezone(
                pytz.FixedOffset(self.original_offset.total_seconds() / 60)
            )
        else:
            return tz_naive_datetime

    @property
    def tz_string(self):
        return self.__tz_string

    def exact_equals(self, other):
        """
        Stricter equality than default __eq__

        In addition to representing the same point in time,
        the two UTCDateTimes must have the same original offset

        """
        if not isinstance(other, type(self)):
            return False
        for attr in self.__ATTRS:
            if getattr(self, attr) != getattr(other, attr):
                return False
        return True

    def __repr__(self):
        return '{}, original_offset={})'.format(
            super(UTCDateTime, self).__repr__()[:-1],
            repr(self.tz_string),
        )

    @staticmethod
    def _validate_tz_offset(hours, minutes, seconds):
        if not (0 <= hours <= 15):
            raise ValueError("Timezone offset "
                             "hours must be between 0 and 14 (inclusive)")
        if minutes not in (0, 15, 30, 45):
            raise ValueError('Timezone offset '
                             'minutes must be in increments of 15')
        if seconds != 0:
            raise ValueError('Timezone offset seconds must be 0')

    @staticmethod
    def tz_offset_to_string(offset):
        if offset is None:
            return None
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
        UTCDateTime._validate_tz_offset(hours, minutes, seconds)
        return '{}{:02d}:{:02d}'.format(sign, hours, minutes)

    @staticmethod
    def tz_string_to_offset(string):
        if string is None:
            return None
        match = UTCDateTime.__TZ_RE.match(string)
        if not match:
            raise ValueError('tz_string must match {}'
                             .format(UTCDateTime.__TZ_RE))
        sign, hours, minutes = match.groups()
        hours = int(hours)
        minutes = int(minutes)
        assert sign in '+-'
        sign = 1 if sign == '+' else -1
        UTCDateTime._validate_tz_offset(hours, minutes, 0)
        return sign * datetime.timedelta(hours=hours, minutes=minutes)
