from __future__ import absolute_import
from calendar import monthrange
from datetime import datetime
from corehq.apps.reports.models import ReportNotification
from corehq.util.soft_assert import soft_assert
from six.moves import range


_soft_assert = soft_assert(exponential_backoff=True)


def get_scheduled_report_ids(period, as_of=None):
    as_of = as_of or datetime.utcnow()
    assert period in ('daily', 'weekly', 'monthly'), period

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
                for day in range(as_of.day + 1, 32):
                    for minute in minutes:
                        yield {
                            'key': [period, as_of.hour, minute, day]
                        }

    try:
        keys = _keys(period, as_of)
    except ValueError:
        _soft_assert(False, "Celery was probably down for a while. Lots of reports are getting dropped!")
        raise StopIteration

    for key in keys:
        for result in ReportNotification.view(
            "reportconfig/all_notifications",
            reduce=False,
            include_docs=False,
            **key
        ).all():
            yield result['id']


def guess_reporting_minute(now=None):
    """
    Tries to guess a report window based on the current time.
    This is super sketchy - will choose a close time to the hour or 30 minute mark or
    fail hard in the event the task is too far from those.

    Only looks forwards in time.
    """
    now = now or datetime.utcnow()
    window = 5

    for reporting_minute in [0, 15, 30, 45]:
        if reporting_minute <= now.minute <= reporting_minute + window:
            return reporting_minute

    raise ValueError("Couldn't guess reporting minute for time: {}".format(now))
