import datetime
from corehq.apps.accounting.utils import get_previous_month_date_range
from corehq.apps.reports.exceptions import InvalidDaterangeException


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
