from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
import decimal
from jsonobject.base_properties import AbstractDateProperty
from jsonobject import *
import re
from jsonobject.api import re_date, re_time, re_decimal
from dimagi.utils.dates import safe_strftime
from dimagi.utils.parsing import ISO_DATETIME_FORMAT
from django.conf import settings


OldJsonObject = JsonObject
OldDateTimeProperty = DateTimeProperty

HISTORICAL_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


try:
    # this isn't actually part of dimagi-utils
    # but this is temporary and don't want to do a bigger reorg
    from corehq.util.soft_assert import soft_assert
except ImportError:
    def _assert(assertion, msg):
        assert assertion, msg
else:
    _assert = soft_assert('{}@{}'.format('droberts', 'dimagi.com'),
                          # should still fail in tests
                          fail_if_debug=settings.UNIT_TESTING)


class DateTimeProperty(AbstractDateProperty):
    """
    Accepts and produces ISO8601 string in UTC (with the Z suffix)
    Accepts with or without microseconds (must have all six digits if any)
    Always produces with microseconds

    (USec stands for microsecond)

    """

    _type = datetime.datetime

    def _wrap(self, value):
        if '.' in value:
            fmt = ISO_DATETIME_FORMAT
            if len(value.split('.')[-1]) != 7:
                raise ValueError(
                    'USecDateTimeProperty '
                    'must have 6 decimal places '
                    'or none at all: {}'.format(value)
                )
        else:
            fmt = HISTORICAL_DATETIME_FORMAT

        try:
            result = datetime.datetime.strptime(value, fmt)
        except ValueError as e:
            raise ValueError(
                'Invalid date/time {0!r} [{1}]'.format(value, e))

        _assert(result.tzinfo is None,
                "USecDateTimeProperty shouldn't ever return offset-aware!")
        return result

    def _unwrap(self, value):
        _assert(value.tzinfo is None,
                "Can't set a USecDateTimeProperty to an offset-aware datetime")
        return value, safe_strftime(value, '%Y-%m-%dT%H:%M:%S.%fZ')


re_trans_datetime = re.compile(r"""
    ^
    (\d{4})  # year
    -
    (0[1-9]|1[0-2])  # month
    -
    ([12]\d|0[1-9]|3[01])  # day
    T
    ([01]\d|2[0-3])  # hour
    :
    [0-5]\d  # minute
    :
    [0-5]\d  # second
    (\.\d{6})?  # millisecond (optional)
    Z  # timezone
    $
""", re.VERBOSE)

# this is like jsonobject.api.re_datetime,
# but without the "time" part being optional
# i.e. I just removed (...)? surrounding the second two lines
re_loose_datetime = re.compile(r"""
    ^
    (\d{4})  # year
    \D?
    (0[1-9]|1[0-2])  # month
    \D?
    ([12]\d|0[1-9]|3[01])  # day
    [ T]
    ([01]\d|2[0-3])  # hour
    \D?
    ([0-5]\d)  # minute
    \D?
    ([0-5]\d)?  # second
    \D?
    (\d{3,6})?  # millisecond
    ([zZ]|([\+-])([01]\d|2[0-3])\D?([0-5]\d)?)?  # timezone
    $
""", re.VERBOSE)


class USecDateTimeMeta(object):
    update_properties = {
        datetime.datetime: DateTimeProperty,
    }
    string_conversions = (
        (re_date, datetime.date),
        (re_time, datetime.time),
        (re_trans_datetime, datetime.datetime),
        (re_decimal, decimal.Decimal),
    )


class JsonObject(OldJsonObject):
    Meta = USecDateTimeMeta


class StrictJsonObject(JsonObject):
    _allow_dynamic_properties = False
