import datetime

from django.conf import settings
from django.core.cache import cache

from corehq.apps.celery import periodic_task
from corehq.celery_monitoring.signals import get_task_time_to_start
from corehq.util.metrics import metrics_gauge
from corehq.util.metrics.const import MPM_MAX

HEARTBEAT_FREQUENCY = datetime.timedelta(seconds=10)
HEARTBEAT_CACHE_TIMEOUT = datetime.timedelta(days=2)


class HeartbeatNeverRecorded(Exception):
    pass


class HeartbeatCache(object):
    def __init__(self, queue):
        self.queue = queue

    def _cache_key(self):
        return 'heartbeat:{}'.format(self.queue)

    def get(self):
        return cache.get(self._cache_key())

    def set(self, value):
        cache.set(self._cache_key(), value, timeout=HEARTBEAT_CACHE_TIMEOUT.total_seconds())

    def delete(self):
        cache.delete(self._cache_key())


class HeartbeatTimeToStartCache(HeartbeatCache):
    def _cache_key(self):
        return f'heartbeat:time_to_start:{self.queue}'


class Heartbeat(object):
    def __init__(self, queue):
        self.queue = queue
        self._heartbeat_cache = HeartbeatCache(queue)
        self._time_to_start_cache = HeartbeatTimeToStartCache(queue)
        self.threshold = settings.CELERY_HEARTBEAT_THRESHOLDS[self.queue]

    def get_last_seen(self):
        value = self._heartbeat_cache.get()
        if value is None:
            raise HeartbeatNeverRecorded()
        else:
            return value

    def mark_seen(self):
        self._heartbeat_cache.set(datetime.datetime.utcnow())

    def clear_last_seen(self):
        """Only used in tests"""
        self._heartbeat_cache.delete()

    def get_blockage_duration(self):
        """
        Estimate the amount of time the queue has been blocked

        :returns a timedelta or raises HeartbeatNeverRecorded
        """
        # Subtract off the time between heartbeats
        # since we don't know how long it's been since the last heartbeat
        return max(datetime.datetime.utcnow() - self.get_last_seen() - HEARTBEAT_FREQUENCY,
                   datetime.timedelta(seconds=0))

    def get_and_report_blockage_duration(self):
        blockage_duration = self.get_blockage_duration()
        metrics_gauge(
            'commcare.celery.heartbeat.blockage_duration',
            blockage_duration.total_seconds(),
            tags={'celery_queue': self.queue},
            multiprocess_mode=MPM_MAX
        )
        if self.threshold:
            metrics_gauge(
                'commcare.celery.heartbeat.blockage_ok',
                1 if blockage_duration.total_seconds() <= self.threshold else 0,
                tags={'celery_queue': self.queue},
                multiprocess_mode=MPM_MAX
            )
        return blockage_duration

    def set_time_to_start(self, task_id):
        time_to_start = get_task_time_to_start(task_id)
        self._time_to_start_cache.set(time_to_start)

    def get_and_report_time_to_start(self):
        time_to_start = self._time_to_start_cache.get()
        if self.threshold:
            metrics_gauge(
                'commcare.celery.heartbeat.time_to_start_ok',
                1 if time_to_start is not None and time_to_start.total_seconds() <= self.threshold else 0,
                tags={'celery_queue': self.queue},
                multiprocess_mode=MPM_MAX
            )
        return time_to_start

    @property
    def periodic_task_name(self):
        return 'heartbeat__{}'.format(self.queue)

    def make_periodic_task(self):
        """
        Create a heartbeat @periodic_task specifically for self.queue

        This is called on python startup so should avoid network calls
        and anything else slow.
        """
        def heartbeat():
            try:
                self.get_and_report_blockage_duration()
                self.set_time_to_start(heartbeat.request.id)
                self.get_and_report_time_to_start()
            except HeartbeatNeverRecorded:
                pass
            self.mark_seen()

        heartbeat.__name__ = str(self.periodic_task_name)

        heartbeat = periodic_task(run_every=HEARTBEAT_FREQUENCY, queue=self.queue, ignore_result=True)(heartbeat)
        return heartbeat
