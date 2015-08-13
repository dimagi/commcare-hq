import datetime
from corehq.apps.accounting.utils import get_previous_month_date_range
from corehq.apps.reports.exceptions import InvalidDaterangeException


DATE_RANGE_CHOICES = [
    'last7',
    'last30',
    'lastn',
    'lastmonth',
    'lastyear',
    'since',
    'range',
    '',
]


def get_daterange_start_end_dates(date_range, start_date=None, end_date=None, days=None):
    today = datetime.date.today()
    if date_range == 'since':
        start_date = start_date
        end_date = today
    elif date_range == 'range':
        start_date = start_date
        end_date = end_date
    elif date_range == 'lastmonth':
        start_date, end_date = get_previous_month_date_range()
    elif date_range == 'lastyear':
        last_year = today.year - 1
        return datetime.date(last_year, 1, 1), datetime.date(last_year, 12, 31)
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
