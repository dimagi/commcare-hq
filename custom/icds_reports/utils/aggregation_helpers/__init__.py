from __future__ import absolute_import
from __future__ import unicode_literals


def transform_day_to_month(day):
    return day.replace(day=1)


def month_formatter(day):
    return transform_day_to_month(day).strftime('%Y-%m-%d')


def date_to_string(date):
    return date.strftime('%Y-%m-%d')


