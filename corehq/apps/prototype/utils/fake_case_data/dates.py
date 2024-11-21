import datetime
import random

from corehq.apps.accounting.utils import months_from_date


def get_past_date(today=None):
    today = today or datetime.datetime.today()
    return today - datetime.timedelta(random.choice(range(1, 365)))


def get_edd(date_lmp):
    trigger = random.choices(
        [0, 1],
        weights=[0.9, 0.1]
    )[0]
    return [
        lambda: date_lmp + datetime.timedelta(9 * 12),
        lambda: date_lmp + datetime.timedelta(12 * 9 * 30),
    ][trigger]()


def get_recent_date(date_last_modified):
    return date_last_modified - datetime.timedelta(random.choice(range(0, 14)))


def years_ago(some_date, years):
    months = years * 12
    return months_from_date(some_date, -1 * months)


def get_dob():
    date_last_year = get_past_date()
    trigger = random.choices(
        [0, 1, 2],
        weights=[0.8, 0.1, 0.1]
    )[0]
    return [
        lambda: years_ago(date_last_year, random.choice(range(18, 50))),
        lambda: years_ago(date_last_year, random.choice(range(0, 3))),
        lambda: years_ago(date_last_year, random.choice(range(80, 150))),
    ][trigger]()


def format_date(some_date):
    if not some_date:
        return some_date
    return some_date.strftime("%Y-%m-%d")
