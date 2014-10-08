from __future__ import absolute_import
import datetime
import iso8601
import re


class UTCDateTime(datetime.datetime):

    __ATTRS = ('year', 'month', 'day', 'hour', 'minute', 'second',
               'microsecond', 'original_offset')
    __TZ_RE = re.compile(r'^([\+-])(\d\d):(\d\d)$')

    def __new__(cls, year, month, day, hour=0, minute=0, second=0,
                microsecond=0, original_offset=datetime.timedelta(0)):

        self = super(UTCDateTime, cls).__new__(cls, year, month, day, hour,
                                               minute, second, microsecond,
                                               tzinfo=None)
        if not isinstance(original_offset, (datetime.timedelta, basestring)):
            raise TypeError('original_offset must be a timedelta or string')
        if isinstance(original_offset, datetime.timedelta):
            self.__original_offset = original_offset
            self.__tz_string = self.tz_offset_to_string(original_offset)
        else:
            # they passed in a '+hh:mm' formatted string as original_offset
            self.__original_offset = self.tz_string_to_offset(original_offset)
            self.__tz_string = original_offset
        return self

    @property
    def tzinfo(self):
        # we can't actually del this attribute, so doing the next best thing
        raise AttributeError("'UTCDateTime' object has no attribute 'tzinfo'")

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
            if original_offset is None:
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
        return self.__tz_string

    def __eq__(self, other):
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
        UTCDateTime._validate_tz_offset(hours, minutes, seconds)
        return '{}{:02d}:{:02d}'.format(sign, hours, minutes)

    @staticmethod
    def tz_string_to_offset(string):
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
