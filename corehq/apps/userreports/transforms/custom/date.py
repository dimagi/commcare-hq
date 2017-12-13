from __future__ import absolute_import
import calendar
from datetime import datetime
from ethiopian_date import EthiopianDateConverter
from dimagi.utils.dates import force_to_datetime


def get_month_display(month_index):
    try:
        return calendar.month_name[int(month_index)]
    except (KeyError, ValueError):
        return ""


def days_elapsed_from_date(date):
    date = force_to_datetime(date)
    now = datetime.utcnow()
    return (now - date).days


def get_ethiopian_to_gregorian(date_string):
    '''
    Takes a string ethiopian date and converts it to
    the equivalent gregorian date

    :param date_string: A date string that is in the format YYYY-MM-DD
    :returns: A gregorian datetime or ''
    '''
    if not date_string:
        return ''

    try:
        year, month, day = date_string.split('-')
        year, month, day = int(year), int(month), int(day)
    except ValueError:
        return ''

    try:
        return EthiopianDateConverter.to_gregorian(year, month, day)
    except Exception:
        return ''
