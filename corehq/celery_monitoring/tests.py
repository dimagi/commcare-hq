from __future__ import absolute_import
from __future__ import print_function

import datetime

from freezegun import freeze_time

from corehq.celery_monitoring.heartbeat import Heartbeat, HeartbeatNeverRecorded, \
    HEARTBEAT_FREQUENCY
from testil import assert_raises, eq


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
