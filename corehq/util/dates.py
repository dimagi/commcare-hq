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
    This hack assumes datetime_fmt does not contain directives whose
    value is dependent on the year, such as week number of the year ('%W').
    The hack allows strftime to be used to support directives such as '%b'.
    """
    assert '%a' not in fmt
    assert '%A' not in fmt
    assert '%w' not in fmt
    assert '%U' not in fmt
    assert '%W' not in fmt
    assert '%c' not in fmt
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
