from __future__ import absolute_import
from __future__ import unicode_literals
from calendar import monthrange
from datetime import datetime
from corehq.apps.saved_reports.models import ReportNotification
from corehq.util.soft_assert import soft_assert
from six.moves import range


_soft_assert = soft_assert(
    to='{}@{}'.format('supportteam', 'dimagi.com'),
    exponential_backoff=False,
)


def _make_all_notification_view_keys(period, target):
    """

    :param period: 'daily', 'weekly', or 'monthly'
    :param target: The 15-minute-aligned point in time we are targeting for a match
    :return: generator of couch view kwargs to use in view query for 'reportconfig/all_notifications'
    """
    assert target.minute % 15 == 0
    assert target.second == 0
    assert target.microsecond == 0

    if target.minute == 0:
        # for legacy purposes, on the hour also include reports that didn't have a minute set
        minutes = (None, target.minute)
    else:
        minutes = (target.minute,)

    if period == 'daily':
        for minute in minutes:
            yield {
                'startkey': [period, target.hour, minute],
                'endkey': [period, target.hour, minute, {}],
            }
    elif period == 'weekly':
        for minute in minutes:
            yield {
                'key': [period, target.hour, minute, target.weekday()],
            }
    else:
        # monthly
        for minute in minutes:
            yield {
                'key': [period, target.hour, minute, target.day]
            }
        if target.day == monthrange(target.year, target.month)[1]:
            for day in range(target.day + 1, 32):
                for minute in minutes:
                    yield {
                        'key': [period, target.hour, minute, day]
                    }


def get_scheduled_report_ids(period, as_of=None):
    as_of = as_of or datetime.utcnow()
    assert period in ('daily', 'weekly', 'monthly'), period

    target_minute = guess_reporting_minute(as_of)
    target_point_in_time = as_of.replace(minute=target_minute, second=0, microsecond=0)
    keys = _make_all_notification_view_keys(period, target_point_in_time)
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
