import datetime
import time
from corehq.util.soft_assert import soft_assert
from dimagi.utils.parsing import ISO_DATE_FORMAT


def unix_time(dt):
    epoch = datetime.datetime.utcfromtimestamp(0)
    delta = dt - epoch
    return delta.total_seconds()


def unix_time_millis(dt):
    return unix_time(dt) * 1000.0


def get_timestamp(date):
    return time.mktime(date.timetuple())


def get_timestamp_millis(date):
    return 1000 * get_timestamp(date)


def safe_strftime(val, fmt):
    """
    conceptually the same as val.strftime(fmt), but this works even with
    dates pre-1900.

    (For some reason, '%Y' and others do not work for pre-1900 dates
    in python stdlib datetime.[date|datetime].strftime.)

    This function strictly asserts that fmt does not contain directives whose
    value is dependent on the year, such as week number of the year ('%W').
    """
    assert '%a' not in fmt  # short weekday name
    assert '%A' not in fmt  # full weekday name
    assert '%w' not in fmt  # weekday (Sun-Sat) as a number (0-6)
    assert '%U' not in fmt  # week number of the year (weeks starting on Sun)
    assert '%W' not in fmt  # week number of the year (weeks starting on Mon)
    assert '%c' not in fmt  # full date and time representation
    assert '%x' not in fmt  # date representation
    assert '%X' not in fmt  # time representation
    # important that our dummy year is a leap year
    # so that it has Feb. 29 in it
    a_leap_year = 2012
    if isinstance(val, datetime.datetime):
        safe_val = datetime.datetime(
            a_leap_year, val.month, val.day, hour=val.hour,
            minute=val.minute, second=val.second,
            microsecond=val.microsecond, tzinfo=val.tzinfo)
    else:
        safe_val = datetime.date(a_leap_year, val.month, val.day)
    return safe_val.strftime(fmt
                             .replace("%Y", str(val.year))
                             .replace("%y", str(val.year)[-2:]))


_assert = soft_assert('droberts' + '@' + 'dimagi.com')


ISO_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def iso_string_to_datetime(iso_string):
    """
    parse datetime string in iso format with or without microseconds,
    always with both date and time
    and always with the 'Z' UTC timezone suffix

    return an offset-naive datetime representing UTC


    >>> iso_string_to_datetime('2015-04-07T19:07:55Z')
    datetime.datetime(2015, 4, 7, 19, 7, 55)
    >>> iso_string_to_datetime('2015-04-07T19:07:55.437086Z')
    datetime.datetime(2015, 4, 7, 19, 7, 55, 437086)

    """
    for fmt in ['%Y-%m-%dT%H:%M:%SZ', ISO_DATETIME_FORMAT]:
        try:
            return datetime.datetime.strptime(iso_string, fmt)
        except ValueError:
            pass
    _assert(False, 'input not in expected format: {!r}'.format(iso_string))
    from dimagi.utils.parsing import string_to_utc_datetime
    return string_to_utc_datetime(iso_string)


def iso_string_to_date(iso_string):
    """
    parse a date string in iso format

    return a datetime.date
    >>> iso_string_to_date('2015-04-07')
    datetime.date(2015, 4, 7)

    """
    return datetime.datetime.strptime(iso_string, ISO_DATE_FORMAT).date()


def datetime_to_iso_string(dt):
    """
    includes microseconds (always)
    >>> datetime_to_iso_string(datetime.datetime(2015, 4, 8, 12, 0, 1))
    '2015-04-08T12:00:01.000000Z'
    """
    assert isinstance(dt, datetime.datetime)
    return dt.strftime(ISO_DATETIME_FORMAT)
