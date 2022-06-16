import datetime

from dimagi.utils.dates import DateSpan


def last_month_dict():
    last_month = get_last_month()
    return {'month': last_month.month, 'year': last_month.year}


def last_month_datespan():
    last_month = get_last_month()
    return DateSpan.from_month(last_month.month, last_month.year)


def get_last_month():
    today = datetime.date.today()
    first_of_this_month = datetime.date(day=1, month=today.month, year=today.year)
    return first_of_this_month - datetime.timedelta(days=1)
