from __future__ import absolute_import
from collections import namedtuple
import datetime
from django.utils.translation import ugettext_lazy as _
from corehq.apps.reports.exceptions import InvalidDaterangeException
from corehq.util.dates import get_current_month_date_range, get_previous_month_date_range, \
    get_current_quarter_date_range, get_previous_quarter_date_range


DateRangeChoice = namedtuple('DateRangeChoice', ['slug', 'description', 'simple'])


def get_all_daterange_choices():
    return (
        DateRangeChoice('last7', _('Last 7 Days'), True),
        DateRangeChoice('last30', _('Last 30 Days'), True),
        DateRangeChoice('lastn', _('Last N Days'), False),
        DateRangeChoice('lastmonth', _('Last Month'), True),
        DateRangeChoice('thisyear', _('This Year'), True),
        DateRangeChoice('lastyear', _('Last Year'), True),
        DateRangeChoice('since', _('Since a Date'), False),
        DateRangeChoice('range', _('Date Range'), False),
        DateRangeChoice('thismonth', _('This Month'), True),
        DateRangeChoice('thisquarter', _('This Quarter'), True),
        DateRangeChoice('lastquarter', _('Last Quarter'), True),
    )


def get_all_daterange_slugs():
    # the empty string is to represent an empty choice
    # we may want to remove it
    return [choice.slug for choice in get_all_daterange_choices()] + ['']


def get_simple_dateranges():
    """
    Get all dateranges that are simple (don't require additional config)
    """
    return filter(lambda choice: choice.simple, get_all_daterange_choices())


def get_daterange_start_end_dates(date_range, start_date=None, end_date=None, days=None):
    today = datetime.date.today()
    if date_range == 'since':
        start_date = start_date
        end_date = today
    elif date_range == 'range':
        start_date = start_date
        end_date = end_date
    elif date_range == 'thismonth':
        start_date, end_date = get_current_month_date_range()
    elif date_range == 'lastmonth':
        start_date, end_date = get_previous_month_date_range()
    elif date_range == 'thisquarter':
        start_date, end_date = get_current_quarter_date_range()
    elif date_range == 'lastquarter':
        start_date, end_date = get_previous_quarter_date_range()
    elif date_range == 'lastyear':
        last_year = today.year - 1
        return datetime.date(last_year, 1, 1), datetime.date(last_year, 12, 31)
    elif date_range == 'thisyear':
        return datetime.date(today.year, 1, 1), datetime.date(today.year, 12, 31)
    else:
        end_date = today
        days = {
            'last7': 7,
            'last30': 30,
            'lastn': days
        }.get(date_range)
        if days is None:
            raise InvalidDaterangeException
        start_date = today - datetime.timedelta(days=days)

    if start_date is None or end_date is None:
        raise InvalidDaterangeException

    return start_date, end_date
