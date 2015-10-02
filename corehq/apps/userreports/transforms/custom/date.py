import calendar
from datetime import datetime
from dimagi.utils.dates import force_to_datetime


def get_month_display(month_index):
    return calendar.month_name[int(month_index)]


def days_elapsed_from_date(date):
    date = force_to_datetime(date)
    now = datetime.utcnow()
    return (now - date).days
