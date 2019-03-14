from __future__ import absolute_import
from __future__ import unicode_literals
import pytz
import re
import six

from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.timezones.conversions import ServerTime
from datetime import datetime, date


def get_date(value):
    if isinstance(value, date):
        if isinstance(value, datetime):
            return value.date()

        return value

    if not isinstance(value, six.string_types):
        raise TypeError("Expected date, datetime, or string")
    soft_assert_type_text(value)

    if not re.match(r'^\d{4}-\d{2}-\d{2}', value):
        raise ValueError("Expected a date string")

    return datetime.strptime(value, '%Y-%m-%d').date()


def todays_date(utc_now):
    return ServerTime(utc_now).user_time(pytz.timezone('Asia/Kolkata')).done().date()
