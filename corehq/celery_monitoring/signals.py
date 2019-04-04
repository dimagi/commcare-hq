import datetime

from celery.signals import after_task_publish, task_prerun
from django.core.cache import cache


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
        try:
            return datetime.datetime.utcnow() - cache.get(self._cache_key)
        except TypeError:
            return None
        finally:
            cache.delete(self._cache_key)


@after_task_publish.connect
def celery_add_time_sent(headers=None, body=None, **kwargs):
    info = headers if 'task' in headers else body
    task_id = info['id']
    TimeToStartTimer(task_id).start_timing()


@task_prerun.connect
def celery_record_time_to_start(task_id=None, task=None, **kwargs):
    from corehq.util.datadog.gauges import datadog_gauge, datadog_counter
    time_to_start = TimeToStartTimer(task_id).stop_and_pop_timing()
    tags = [
        'celery_task_name:{}'.format(task.name),
        'celery_queue:{}'.format(task.queue),
    ]
    if time_to_start:
        datadog_gauge('commcare.celery.task.time_to_start', time_to_start.total_seconds(), tags=tags)
    else:
        datadog_counter('commcare.celery.task.time_to_start_unavailable', tags=tags)
