from __future__ import absolute_import
import datetime
import decimal
from jsonobject import AbstractDateProperty
import re
from jsonobject.api import re_date, re_time, re_decimal


HISTORICAL_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
TARGET_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'


class TransitionalExactDateTimeProperty(AbstractDateProperty):
    """
    Accepts HISTORICAL_DATETIME_FORMAT or TARGET_DATETIME_FORMAT as input
    always produces TARGET_DATETIME_FORMAT as output

    """

    _type = datetime.datetime

    def _wrap(self, value):
        if '.' in value:
            fmt = TARGET_DATETIME_FORMAT
            if len(value.split('.')[-1]) != 7:
                raise ValueError(
                    'TransitionalExactDateTimeProperty '
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

        assert result.tzinfo is None
        return result

    def _unwrap(self, value):
        assert value.tzinfo is None
        return value, value.strftime('%Y-%m-%dT%H:%M:%S.%fZ')


re_trans_datetime = re.compile(r'^\d{4}-0[1-9]|1[0-2]-[12]\d|0[1-9]|3[01]T'
                               r'[01]\d|2[0-3]:[0-5]\d:[0-5]\d(\.\d{6})?Z$')

# this is like jsonobject.api.re_datetime,
# but without the "time" part being optional
# i.e. I just removed (...)? surrounding the second two lines
re_loose_datetime = re.compile(
    r'^(\d{4})\D?(0[1-9]|1[0-2])\D?([12]\d|0[1-9]|3[01])'
    r'\D?([01]\d|2[0-3])\D?([0-5]\d)\D?([0-5]\d)?\D?(\d{3,6})?'
    r'([zZ]|([\+-])([01]\d|2[0-3])\D?([0-5]\d)?)?$'
)

class TransDateTimeMeta(object):
    update_properties = {
        datetime.datetime: TransitionalExactDateTimeProperty,
    }
    string_conversions = (
        (re_date, datetime.date),
        (re_time, datetime.time),
        (re_trans_datetime, datetime.datetime),
        (re_decimal, decimal.Decimal),
    )
