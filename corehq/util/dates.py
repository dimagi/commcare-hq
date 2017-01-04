import calendar
import datetime
import time

from dimagi.utils.dates import add_months
from dimagi.utils.parsing import ISO_DATE_FORMAT, ISO_DATETIME_FORMAT


def unix_time(dt):
    epoch = datetime.datetime.utcfromtimestamp(0)
    delta = dt - epoch
    return delta.total_seconds()


def get_timestamp(date):
    return time.mktime(date.timetuple())


def get_timestamp_millis(date):
    return 1000 * get_timestamp(date)


def iso_string_to_datetime(iso_string, strict=False):
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

    if strict:
        raise ValueError('iso_string_to_datetime input not in expected format: {}'.format(iso_string))
    else:
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


def get_first_last_days(year, month):
    last_day = calendar.monthrange(year, month)[1]
    date_start = datetime.date(year, month, 1)
    date_end = datetime.date(year, month, last_day)
    return date_start, date_end


def get_current_month_date_range(reference_date=None):
    reference_date = reference_date or datetime.date.today()
    date_start = datetime.date(reference_date.year, reference_date.month, 1)
    return date_start, reference_date


def get_previous_month_date_range(reference_date=None):
    reference_date = reference_date or datetime.date.today()

    last_month_year, last_month = add_months(reference_date.year, reference_date.month, -1)
    return get_first_last_days(last_month_year, last_month)


def get_quarter_date_range(year, quarter):
    """
    Returns a daterange for the quarter, that ends on the _first_ of the following month..
    """
    assert quarter in (1, 2, 3, 4)
    return (
        datetime.datetime(year, quarter * 3 - 2, 1),
        datetime.datetime(year + quarter * 3 / 12, (quarter * 3 + 1) % 12, 1)
    )


def get_quarter_for_date(date):
    quarter = (date.month - 1) / 3 + 1
    return date.year, quarter


def get_current_quarter_date_range():
    return get_quarter_date_range(*get_quarter_for_date(datetime.datetime.utcnow()))


def get_previous_quarter_date_range():
    year, quarter = get_quarter_for_date(datetime.datetime.utcnow())
    if quarter == 1:
        return get_quarter_date_range(year - 1, 4)
    else:
        return get_quarter_date_range(year, quarter - 1)
