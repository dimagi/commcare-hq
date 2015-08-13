from datetime import datetime
from . import dbaccessors
from .models import DAILY, WEEKLY, MONTHLY, DEFAULT_HOUR, DEFAULT_WEEK_DAY, DEFAULT_MONTH_DAY


def get_message_configs_at_this_hour(as_of=None):
    now = as_of or datetime.utcnow()

    def _get_daily_messages():
        return dbaccessors.by_interval({
            'key': [DAILY, now.hour, DEFAULT_WEEK_DAY, DEFAULT_MONTH_DAY]
        })

    def _get_weekly_messages():
        return dbaccessors.by_interval({
            'key': [WEEKLY, DEFAULT_HOUR, now.weekday(), DEFAULT_MONTH_DAY]
        })

    def _get_monthly_messages():
        return dbaccessors.by_interval({
            'key': [MONTHLY, DEFAULT_HOUR, DEFAULT_WEEK_DAY, now.day]
        })

    return _get_daily_messages() + _get_weekly_messages() + _get_monthly_messages()
