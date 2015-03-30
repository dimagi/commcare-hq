import datetime
import time


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
    return safe_val.strftime(fmt.replace("%Y", str(val.year)))
