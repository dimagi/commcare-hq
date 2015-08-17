from datetime import datetime
from . import dbaccessors
from .models import DAILY, WEEKLY, MONTHLY, DEFAULT_HOUR, DEFAULT_WEEK_DAY, DEFAULT_MONTH_DAY


def get_message_configs_at_this_hour(as_of=None):
    as_of = as_of or datetime.utcnow()
    return get_daily_messages(as_of) + get_weekly_messages(as_of) + get_monthly_messages(as_of)


def get_daily_messages(as_of):
    return dbaccessors.by_interval([
        DAILY, as_of.hour
    ])


def get_weekly_messages(as_of):
    return dbaccessors.by_interval([
        WEEKLY, as_of.weekday(), as_of.hour
    ])


def get_monthly_messages(as_of):
    return dbaccessors.by_interval([
        MONTHLY, as_of.day, as_of.hour
    ])
