"""
MOTECH modules can update the `serializers` dictionary to register
their own serializer functions.

They would do something like the following::

    from corehq.motech.serializers import serializers
    serializers.update({
        (from_data_type, to_data_type): serializer_function,
    })

Serializer functions accept a value in `from_data_type`, and return a
value in `to_data_type`.

"""
import datetime
import re

from dateutil import parser as dateutil_parser

from corehq.motech.const import (
    COMMCARE_DATA_TYPE_DECIMAL,
    COMMCARE_DATA_TYPE_INTEGER,
    COMMCARE_DATA_TYPE_TEXT,
)


def to_decimal(value):
    try:
        return float(value)
    except ValueError:
        return None


def to_integer(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_text(value):
    if value is None:
        return ''
    if not isinstance(value, str):
        return str(value)
    return value


def to_date_str(value):
    """
    Drop the time and timezone to export date-only values

    >>> to_date_str('2017-06-27T12:00:00+0530')
    '2017-06-27'

    """
    if isinstance(value, str):
        if not re.match(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('"{}" is not recognised as a date or a datetime'.format(value))
        value = dateutil_parser.parse(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.strftime('%Y-%m-%d')


serializers = {
    # (from_data_type, to_data_type): function
    (None, COMMCARE_DATA_TYPE_DECIMAL): to_decimal,
    (None, COMMCARE_DATA_TYPE_INTEGER): to_integer,
    (None, COMMCARE_DATA_TYPE_TEXT): to_text,
}
