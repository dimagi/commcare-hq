from datetime import date, time, datetime
from dateutil.parser import parse
import dateutil.tz


TRUE_STRINGS = ("true", "t", "yes", "y", "1")
FALSE_STRINGS = ("false", "f", "no", "n", "0")


def string_to_boolean(val):
    """
    A very dumb string to boolean converter.  Will fail hard
    if the conversion doesn't succeed.
    """
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if val.lower().strip() in TRUE_STRINGS:
        return True
    elif val.lower().strip() in FALSE_STRINGS:
        return False
    raise ValueError("%s is not a parseable boolean!" % val)


def string_to_datetime(val):
    """
    Try to convert a string to a date.
    """
    if isinstance(val, datetime):
        return val
    elif isinstance(val, date):
        return datetime.combine(val, time())
    return parse(val)


def string_to_utc_datetime(val):
    val = string_to_datetime(val)
    if val.tzinfo is None:
        return val
    return val.astimezone(dateutil.tz.tzutc()).replace(tzinfo=None)


ISO_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
ISO_DATE_FORMAT = '%Y-%m-%d'


def json_format_datetime(dt):
    """
    includes microseconds (always)
    >>> json_format_datetime(datetime(2015, 4, 8, 12, 0, 1))
    '2015-04-08T12:00:01.000000Z'

    Offset-aware datetimes are converted to UTC
    >>> kolkata = dateutil.tz.gettz('Asia/Kolkata')
    >>> json_format_datetime(datetime(2015, 4, 8, 12, 0, 1, tzinfo=kolkata))
    '2015-04-08T06:30:01.000000Z'
    """
    from dimagi.ext.jsonobject import _assert
    _assert(isinstance(dt, datetime),
            'json_format_datetime expects a datetime: {!r}'.format(dt))
    if isinstance(dt, datetime) and dt.tzinfo is not None:
        dt = dt.astimezone(dateutil.tz.tzutc()).replace(tzinfo=None)
    return dt.strftime(ISO_DATETIME_FORMAT)


def json_format_date(date_):
    return date_.strftime(ISO_DATE_FORMAT)
