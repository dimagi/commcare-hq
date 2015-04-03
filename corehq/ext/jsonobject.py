from __future__ import absolute_import
import datetime
import decimal
from jsonobject import AbstractDateProperty
import re
from jsonobject.api import re_date, re_time, re_decimal


class TransitionalExactDateTimeProperty(AbstractDateProperty):
    """
    Accepts '%Y-%m-%dT%H:%M:%SZ' or '%Y-%m-%dT%H:%M:%S.%fZ' as input
    always produces '%Y-%m-%dT%H:%M:%S.%fZ' as output

    """

    _type = datetime.datetime

    def _wrap(self, value):
        if '.' in value:
            fmt = '%Y-%m-%dT%H:%M:%S.%fZ'
            if len(value.split('.')[-1]) != 7:
                raise ValueError(
                    'TransitionalExactDateTimeProperty '
                    'must have 6 decimal places '
                    'or none at all: {}'.format(value)
                )
        else:
            fmt = '%Y-%m-%dT%H:%M:%SZ'

        try:
            return datetime.datetime.strptime(value, fmt)
        except ValueError as e:
            raise ValueError(
                'Invalid date/time {0!r} [{1}]'.format(value, e))

    def _unwrap(self, value):
        return value, value.strftime('%Y-%m-%dT%H:%M:%S.%fZ')


re_trans_datetime = re.compile(r'^\d{4}-0[1-9]|1[0-2]-[12]\d|0[1-9]|3[01]T'
                               r'[01]\d|2[0-3]:[0-5]\d:[0-5]\d(\.\d{6})?Z$')


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
