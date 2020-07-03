import datetime

from celery.signals import before_task_publish, task_prerun, task_postrun
from django.core.cache import cache

from corehq.util.quickcache import quickcache
from dimagi.utils.parsing import string_to_utc_datetime


@quickcache(['task_id'])
def get_task_time_to_start(task_id):
    pass  # Actual values are set by the celery event hooks below


class TimingNotAvailable(Exception):
    pass


class CeleryTimer(object):
    def __init__(self, task_id, timing_type):
        self.task_id = task_id
        self.timing_type = timing_type

    @property
    def _cache_key(self):
        return 'task.{}.{}'.format(self.task_id, self.timing_type)

    def start_timing(self, eta=None):
        cache.set(self._cache_key, eta or datetime.datetime.utcnow(), timeout=3 * 24 * 60 * 60)

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

    @staticmethod
    def parse_iso8601(datetime_string):
        return string_to_utc_datetime(datetime_string)


class TimeToStartTimer(CeleryTimer):
    def __init__(self, task_id):
        super(TimeToStartTimer, self).__init__(task_id, timing_type='time_sent')


class TimeToRunTimer(CeleryTimer):
    def __init__(self, task_id):
        super(TimeToRunTimer, self).__init__(task_id, timing_type='time_started')


@before_task_publish.connect
def celery_add_time_sent(headers=None, body=None, **kwargs):
    info = headers if 'task' in headers else body
    task_id = info['id']
    eta = info['eta']
    if eta:
        eta = TimeToStartTimer.parse_iso8601(eta)
    TimeToStartTimer(task_id).start_timing(eta)


@task_prerun.connect
def celery_record_time_to_start(task_id=None, task=None, **kwargs):
    from corehq.util.metrics import metrics_counter, metrics_gauge
    from corehq.util.metrics.const import MPM_MAX

    tags = {
        'celery_task_name': task.name,
        'celery_queue': task.queue,
    }

    timer = TimeToStartTimer(task_id)
    try:
        time_to_start = timer.stop_and_pop_timing()
    except TimingNotAvailable:
        metrics_counter('commcare.celery.task.time_to_start_unavailable', tags=tags)
    else:
        metrics_gauge('commcare.celery.task.time_to_start', time_to_start.total_seconds(), tags=tags,
            multiprocess_mode=MPM_MAX)
        get_task_time_to_start.set_cached_value(task_id).to(time_to_start)

    TimeToRunTimer(task_id).start_timing()


@task_postrun.connect
def celery_record_time_to_run(task_id=None, task=None, state=None, **kwargs):
    from corehq.util.metrics import metrics_counter, metrics_histogram, DAY_SCALE_TIME_BUCKETS

    get_task_time_to_start.clear(task_id)

    tags = {
        'celery_task_name': task.name,
        'celery_queue': task.queue,
        'state': state,
    }
    timer = TimeToRunTimer(task_id)
    try:
        time_to_run = timer.stop_and_pop_timing()
    except TimingNotAvailable:
        metrics_counter('commcare.celery.task.time_to_run_unavailable', tags=tags)
    else:
        metrics_histogram(
            'commcare.celery.task.time_to_run.seconds', time_to_run.total_seconds(),
            bucket_tag='duration', buckets=DAY_SCALE_TIME_BUCKETS, bucket_unit='s',
            tags=tags
        )
