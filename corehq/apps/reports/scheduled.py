from calendar import monthrange
import datetime
from corehq.apps.reports.models import ReportNotification


def get_scheduled_reports(period, as_of=None):
    as_of = as_of or datetime.utcnow()
    assert period in ('daily', 'weekly', 'monthly')

    def _keys(period, as_of):
        minute = guess_reporting_minute(as_of)
        if minute == 0:
            # for legacy purposes, on the hour also include reports that didn't have a minute set
            minutes = (None, minute)
        else:
            minutes = (minute,)

        if period == 'daily':
            for minute in minutes:
                yield {
                    'startkey': [period, as_of.hour, minute],
                    'endkey': [period, as_of.hour, minute, {}],
                }
        elif period == 'weekly':
            for minute in minutes:
                yield {
                    'key': [period, as_of.hour, minute, as_of.weekday()],
                }
        else:
            # monthly
            for minute in minutes:
                yield {
                    'key': [period, as_of.hour, minute, as_of.day]
                }
            if as_of.day == monthrange(as_of.year, as_of.month)[1]:
                for day in range(as_of.day + 1, 31):
                    yield {
                        'key': [period, as_of.hour, day],
                    }

    for keys in _keys(period, as_of):
        for report in ReportNotification.view("reportconfig/all_notifications",
            reduce=False,
            include_docs=True,
            **keys
        ).all():
            yield report


def guess_reporting_minute(now=None):
    """
    Tries to guess a report window based on the current time.
    This is super sketchy - will choose a close time to the hour or 30 minute mark or
    fail hard in the event the task is too far from those.

    Only looks forwards in time.
    """
    now = now or datetime.utcnow()
    window = 5
    if now.minute <= window:
        return 0
    elif 30 <= now.minute <= 35:
        return 30

    raise ValueError("Couldn't guess reporting minute for time: {}".format(now))
