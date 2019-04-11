from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from django.conf import settings

import datetime

from freezegun import freeze_time

from corehq.celery_monitoring.heartbeat import Heartbeat, HeartbeatNeverRecorded, \
    HEARTBEAT_FREQUENCY
from testil import assert_raises, eq

from corehq.celery_monitoring.signals import TimeToStartTimer, TimingNotAvailable


def test_heartbeat():
    hb = Heartbeat('celery_periodic')
    hb.clear_last_seen()

    with assert_raises(HeartbeatNeverRecorded):
        hb.get_last_seen()

    with assert_raises(HeartbeatNeverRecorded):
        hb.get_blockage_duration()

    seen_time = datetime.datetime.utcnow()

    with freeze_time(seen_time):
        hb.mark_seen()
        eq(hb.get_last_seen(), seen_time)
        eq(hb.get_blockage_duration(), datetime.timedelta(seconds=0))

    with freeze_time(seen_time + datetime.timedelta(minutes=10)):
        eq(hb.get_last_seen(), seen_time)
        eq(hb.get_blockage_duration(), datetime.timedelta(minutes=10) - HEARTBEAT_FREQUENCY)


def test_get_and_report_blockage_duration():
    hb = Heartbeat('celery_periodic')
    hb.mark_seen()
    # just assert that this doesn't error
    hb.get_and_report_blockage_duration()


def test_time_to_start_timer():
    task_id = 'abc123'
    delay = datetime.timedelta(seconds=6)

    start_time = datetime.datetime.utcnow()

    # starts empty
    with assert_raises(TimingNotAvailable):
        TimeToStartTimer(task_id).stop_and_pop_timing()

    with freeze_time(start_time):
        TimeToStartTimer(task_id).start_timing(datetime.datetime.utcnow())

    with freeze_time(start_time + delay):
        time_to_start = TimeToStartTimer(task_id).stop_and_pop_timing()

    eq(time_to_start, delay)

    # can only pop once, second time empty
    with assert_raises(TimingNotAvailable):
        TimeToStartTimer(task_id).stop_and_pop_timing()


def test_time_to_start_timer_with_eta():
    task_id = 'abc1234'
    delay = datetime.timedelta(seconds=6)

    start_time = datetime.datetime.utcnow()
    eta = start_time + datetime.timedelta(minutes=5)

    with freeze_time(start_time):
        TimeToStartTimer(task_id).start_timing(eta)

    with freeze_time(eta + delay):
        time_to_start = TimeToStartTimer(task_id).stop_and_pop_timing()

    eq(time_to_start, delay)


def test_parse_iso8601():
    eq(TimeToStartTimer.parse_iso8601('2009-11-17T12:30:56.527191'),
       datetime.datetime(2009, 11, 17, 12, 30, 56, 527191))


def test_import_tasks():
    from . import tasks
    for queue in settings.CELERY_HEARTBEAT_THRESHOLDS:
        # assert each heartbeat task is there
        getattr(tasks, Heartbeat(queue).periodic_task_name)
