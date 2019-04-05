from __future__ import absolute_import
from __future__ import unicode_literals
import datetime

from celery.signals import before_task_publish, task_prerun
from django.core.cache import cache


class TimingNotAvailable(Exception):
    pass


class TimeToStartTimer(object):
    def __init__(self, task_id):
        self.task_id = task_id

    @property
    def _cache_key(self):
        return 'task.{}.time_sent'.format(self.task_id)

    def start_timing(self):
        cache.set(self._cache_key, datetime.datetime.utcnow(), timeout=3 * 24 * 60 * 60)

    def stop_and_pop_timing(self):
        """
        Return timedelta since running start_timing

        Only the first call to stop_and_pop_timing will return a timedelta;
        subsequent calls will return None until the next time start_timing is called.

        This helps avoid double-recording timings (for example when a task is retried).
        """
        time_sent = cache.get(self._cache_key)
        if time_sent is None:
            raise TimingNotAvailable()

        cache.delete(self._cache_key)

        return datetime.datetime.utcnow() - time_sent


@before_task_publish.connect
def celery_add_time_sent(headers=None, body=None, **kwargs):
    info = headers if 'task' in headers else body
    task_id = info['id']
    TimeToStartTimer(task_id).start_timing()


@task_prerun.connect
def celery_record_time_to_start(task_id=None, task=None, **kwargs):
    from corehq.util.datadog.gauges import datadog_gauge, datadog_counter

    tags = [
        'celery_task_name:{}'.format(task.name),
        'celery_queue:{}'.format(task.queue),
    ]

    timer = TimeToStartTimer(task_id)
    try:
        time_to_start = timer.stop_and_pop_timing()
    except TimingNotAvailable:
        datadog_counter('commcare.celery.task.time_to_start_unavailable', tags=tags)
    else:
        datadog_gauge('commcare.celery.task.time_to_start', time_to_start.total_seconds(), tags=tags)
