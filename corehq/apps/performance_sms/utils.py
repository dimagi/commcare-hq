from datetime import datetime
from . import dbaccessors
from .models import DAILY, WEEKLY, MONTHLY


def get_message_configs_at_this_hour(as_of=None):

    now = as_of or datetime.utcnow()

    def _keys(period, now):
        if period == DAILY:
            yield {
                'key': [period, now.hour],
            }
        elif period == WEEKLY:
            yield {
                'key': [period, 1, now.weekday()],
            }
        else:
            # monthly
            yield {
                'key': [period, 1, 1, now.day]
            }

    for period in (DAILY, WEEKLY, MONTHLY):
        for keys in _keys(period, now):
            for config in dbaccessors.by_interval(keys):
                yield config
