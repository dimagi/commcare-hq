from __future__ import absolute_import
from __future__ import unicode_literals
import calendar
from datetime import datetime
from ethiopian_date import EthiopianDateConverter
from dimagi.utils.dates import force_to_datetime
import sys


def get_month_display(month_index):
    try:
        return calendar.month_name[int(month_index)]
    except (KeyError, ValueError):
        return ""


def days_elapsed_from_date(date):
    date = force_to_datetime(date)
    now = datetime.utcnow()
    return (now - date).days


def split_date_string(date_string):
    '''
    Takes a date string and splits it up into its component year, month, and day
    :param date_string: A date string that is in the format YYYY-MM-DD
    :return: a tuple containing (year, month, day)
    '''
    year, month, day = date_string.split('-')
    year, month, day = int(year), int(month), int(day)
    return year, month, day


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
        year, month, day = split_date_string(date_string)
    except ValueError:
        return ''

    try:
        return EthiopianDateConverter.to_gregorian(year, month, day)
    except Exception:
        return ''


def get_gregorian_to_ethiopian(date_string):
    '''
    Takes a string gregorian date and converts it to
    the equivalent ethiopian date

    :param date_string: A date string that is in the format YYYY-MM-DD
    :returns: An ethiopian datetime or ''
    '''
    if not date_string:
        return ''

    try:
        year, month, day = split_date_string(date_string)
    except ValueError:
        return ''

    try:
        sys.stderr.write("about to run date converter")
        ethiopian_year, ethiopian_month, ethiopian_day = EthiopianDateConverter.to_ethiopian(year, month, day)
        return '{:02d}-{:02d}-{:02d}'.format(ethiopian_year, ethiopian_month, ethiopian_day)
    except Exception:
        return ''
