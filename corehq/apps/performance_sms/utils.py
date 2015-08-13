from datetime import datetime
from . import dbaccessors


def get_message_configs_at_this_hour():

    now = datetime.utcnow()

    def _keys(period, now):
        if period == 'daily':
            yield {
                'key': [period, now.hour],
            }
        elif period == 'weekly':
            yield {
                'key': [period, 1, now.weekday()],
            }
        else:
            # monthly
            yield {
                'key': [period, 1, 1, now.day]
            }

    for period in ('daily', 'weekly', 'monthly'):
        for keys in _keys(period, now):
            for config in dbaccessors.by_interval(keys).all():
                yield config
