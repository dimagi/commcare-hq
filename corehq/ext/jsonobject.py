from __future__ import absolute_import
import datetime
from jsonobject import AbstractDateProperty


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
