from datetime import date, timedelta

from simpleeval import DEFAULT_FUNCTIONS


def safe_range(start, *args):
    ret = list(range(start, *args))
    if len(ret) < 100:
        return ret
    return None


FUNCTIONS = DEFAULT_FUNCTIONS
FUNCTIONS.update({
    'timedelta_to_seconds': lambda x: x.total_seconds() if isinstance(x, timedelta) else None,
    'range': safe_range,
    'today': date.today,
    'days': lambda t: t.days,
    'round': round
})
