from __future__ import absolute_import
from __future__ import print_function

import datetime

from celery.task import periodic_task

from corehq.util.datadog.gauges import datadog_gauge
from corehq.util.quickcache import quickcache


HEARTBEAT_FREQUENCY = datetime.timedelta(seconds=10)
HEARTBEAT_CACHE_TIMEOUT = datetime.timedelta(days=2)


class HeartbeatNeverRecorded(Exception):
    pass


class Heartbeat(object):
    def __init__(self, queue):
        self.queue = queue

    @quickcache(['self.queue'], timeout=HEARTBEAT_CACHE_TIMEOUT.total_seconds())
    def get_last_seen(self):
        # This function relies on the cache getting set manually in mark_seen
        raise HeartbeatNeverRecorded()

    def mark_seen(self):
        self.get_last_seen.set_cached_value(self).to(datetime.datetime.utcnow())

    def get_blockage_duration(self):
        """
        Estimate the amount of time the queue has been blocked

        :returns a timedelta or raises HeartbeatNeverRecorded
        """
        # Subtract off the time between heartbeats
        # since we don't know how long it's been since the last heartbeat
        return max(datetime.datetime.utcnow() - self.get_last_seen() - HEARTBEAT_FREQUENCY,
                   datetime.timedelta(seconds=0))

    @property
    def periodic_task_name(self):
        return 'heartbeat__{}'.format(self.queue)

    def make_periodic_task(self):
        queue = self.queue

        def heartbeat():
            hb = Heartbeat(queue)
            try:
                datadog_gauge(
                    'commcare.celery.heartbeat.blockage_duration',
                    hb.get_blockage_duration(),
                    tags=['celery_queue:{}'.format(queue)]
                )
            except HeartbeatNeverRecorded:
                pass
            hb.mark_seen()

        heartbeat.func_name = self.periodic_task_name
        heartbeat.__name__ = self.periodic_task_name

        heartbeat = periodic_task(run_every=HEARTBEAT_FREQUENCY, queue=queue)(heartbeat)
        return heartbeat
