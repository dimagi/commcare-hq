import datetime
import re

from dateutil import parser as dateutil_parser

from corehq.motech.const import (
    COMMCARE_DATA_TYPE_DATE,
    COMMCARE_DATA_TYPE_TEXT,
)
from corehq.motech.openmrs.const import (
    OPENMRS_DATA_TYPE_BOOLEAN,
    OPENMRS_DATA_TYPE_DATE,
    OPENMRS_DATA_TYPE_DATETIME,
)
from corehq.motech.serializers import serializers, to_date_str


def to_omrs_date(value):
    """
    Drop the time and timezone to export date-only values

    >>> to_omrs_date('2017-06-27T12:00:00+0530')
    '2017-06-27'

    """
    if isinstance(value, str):
        if not re.match(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('"{}" is not recognised as a date or a datetime'.format(value))
        value = dateutil_parser.parse(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.strftime('%Y-%m-%d')


def to_omrs_datetime(value):
    """
    Converts CommCare dates and datetimes to OpenMRS datetimes.

    >>> to_omrs_datetime('2017-06-27')
    '2017-06-27T00:00:00.000+0000'

    """
    if isinstance(value, str):
        if not re.match(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('"{}" is not recognised as a date or a datetime'.format(value))
        value = dateutil_parser.parse(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        micros = value.strftime('%f')[:3]  # Only 3 digits for OpenMRS
        tz = value.strftime('%z') or '+0000'  # If we don't know, lie
        return value.strftime('%Y-%m-%dT%H:%M:%S.{f}{z}'.format(f=micros, z=tz))


def to_omrs_boolean(value):
    if isinstance(value, str) and value.lower() in ('false', '0'):
        return False
    return bool(value)


def omrs_datetime_to_date(value):
    """
    Converts an OpenMRS datetime to a CommCare date

    >>> omrs_datetime_to_date('2017-06-27T00:00:00.000+0000')
    '2017-06-27'

    """
    if value and 'T' in value:
        return value.split('T')[0]
    return value


def omrs_boolean_to_text(value):
    return 'true' if value else 'false'


def openmrs_timestamp_to_isoformat(value, tz=None):
    """
    Converts an OpenMRS timestamp to ISO format. Accepts a timezone,
    which defaults to UTC. If timezone is given, ISO format includes the
    offset, otherwise it ends in "Z".

    An OpenMRS timestamp is a Unix timestamp * 1000 (i.e. with
    milliseconds). Given None returns None. Raises ValueError for
    non-numeric values.

    >>> openmrs_timestamp_to_isoformat(1551564000000)
    '2019-03-02T22:00:00Z'
    >>> tz = datetime.timezone(datetime.timedelta(hours=+2), 'CAT')
    >>> openmrs_timestamp_to_isoformat(1551564000000, tz)
    '2019-03-03T00:00:00+02:00'
    >>> openmrs_timestamp_to_isoformat(1551564000)
    '2019-03-02T22:00:00Z'

    """
    if value is None:
        return None
    try:
        timestamp = int(value)
    except ValueError:
        raise ValueError(f"{value!r} is not an OpenMRS timestamp")
    max_seconds = datetime.datetime(datetime.MAXYEAR, 12, 31).timestamp()
    seconds_since_1970 = timestamp / 1000 if timestamp > max_seconds else timestamp
    dt = datetime.datetime.fromtimestamp(seconds_since_1970, tz)
    isoformat = dt.isoformat()
    if not dt.utcoffset():
        isoformat += "Z"
    return isoformat


serializers.update({
    # (from_data_type, to_data_type): function
    (None, OPENMRS_DATA_TYPE_DATE): to_date_str,
    (None, OPENMRS_DATA_TYPE_DATETIME): to_omrs_datetime,
    (None, OPENMRS_DATA_TYPE_BOOLEAN): to_omrs_boolean,
    (OPENMRS_DATA_TYPE_DATETIME, COMMCARE_DATA_TYPE_DATE): omrs_datetime_to_date,
    (OPENMRS_DATA_TYPE_BOOLEAN, COMMCARE_DATA_TYPE_TEXT): omrs_boolean_to_text,
})
