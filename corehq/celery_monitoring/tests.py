from __future__ import absolute_import
from __future__ import print_function

import datetime

from freezegun import freeze_time

from corehq.celery_monitoring.heartbeat import Heartbeat, HeartbeatNeverRecorded, \
    HEARTBEAT_FREQUENCY
from testil import assert_raises, eq

from corehq.celery_monitoring.signals import TimeToStartTimer


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


def test_time_to_start_timer():
    task_id = 'abc123'
    delay = datetime.timedelta(seconds=6)

    start_time = datetime.datetime.utcnow()

    # starts empty
    eq(TimeToStartTimer(task_id).stop_and_pop_timing(), None)

    with freeze_time(start_time):
        TimeToStartTimer(task_id).start_timing()

    with freeze_time(start_time + delay):
        time_to_start = TimeToStartTimer(task_id).stop_and_pop_timing()

    eq(time_to_start, delay)
    # can only pop once, second time empty
    eq(TimeToStartTimer(task_id).stop_and_pop_timing(), None)
