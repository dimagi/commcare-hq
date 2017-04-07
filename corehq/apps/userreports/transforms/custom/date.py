import calendar
from datetime import datetime
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
