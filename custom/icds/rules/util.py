import pytz
import re
from datetime import datetime, date

from corehq.util.timezones.conversions import ServerTime


def get_date(value):
    if isinstance(value, date):
        if isinstance(value, datetime):
            return value.date()
        return value

    if not isinstance(value, str):
        raise TypeError("Expected date, datetime, or string")

    if not re.match(r'^\d{4}-\d{2}-\d{2}', value):
        raise ValueError("Expected a date string")

    return datetime.strptime(value, '%Y-%m-%d').date()


def todays_date(utc_now):
    return ServerTime(utc_now).user_time(pytz.timezone('Asia/Kolkata')).done().date()
