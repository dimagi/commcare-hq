from datetime import datetime, timedelta

from django.conf import settings

from celery import chord
from celery.schedules import crontab
from celery.utils.log import get_task_logger

from dimagi.utils.couch import get_redis_lock

from corehq.apps.celery import periodic_task, task
from corehq.motech.models import RequestLog
from corehq.util.metrics import (
    make_buckets_from_timedeltas,
    metrics_counter,
    metrics_gauge_task,
    metrics_histogram_timer,
)
from corehq.util.metrics.const import MPM_MAX
from corehq.util.timer import TimingContext

from ..rate_limiter import rate_limit_repeater, report_repeater_usage
from .const import (
    CHECK_REPEATERS_INTERVAL,
    CHECK_REPEATERS_KEY,
    State,
)
from .models import Repeater, RepeatRecord

_check_repeaters_buckets = make_buckets_from_timedeltas(
    timedelta(seconds=10),
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(hours=1),
    timedelta(hours=5),
    timedelta(hours=10),
)
logging = get_task_logger(__name__)

DELETE_CHUNK_SIZE = 5000


@periodic_task(
    run_every=crontab(hour=6, minute=0),
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def delete_old_request_logs():
    """
    Delete RequestLogs older than 6 weeks
    """
    ninety_days_ago = datetime.utcnow() - timedelta(days=42)
    while True:
        queryset = (RequestLog.objects
                    .filter(timestamp__lt=ninety_days_ago)
                    .values_list('id', flat=True)[:DELETE_CHUNK_SIZE])
        id_list = list(queryset)
        deleted, __ = RequestLog.objects.filter(id__in=id_list).delete()
        if not deleted:
            return


@periodic_task(
    run_every=CHECK_REPEATERS_INTERVAL,
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def check_repeaters():
    start = datetime.utcnow()
    twentythree_hours_sec = 23 * 60 * 60
    twentythree_hours_later = start + timedelta(hours=23)

    # Long timeout to allow all waiting repeaters to be iterated
    # TODO: Check how long it takes to iterate all repeaters on prod
    check_repeater_lock = get_redis_lock(
        CHECK_REPEATERS_KEY,
        timeout=twentythree_hours_sec,
        name=CHECK_REPEATERS_KEY,
    )
    if not check_repeater_lock.acquire(blocking=False):
        metrics_counter("commcare.repeaters.check.locked_out")
        return

    try:
        with metrics_histogram_timer(
            "commcare.repeaters.check.processing",
            timing_buckets=_check_repeaters_buckets,
        ):
            for repeater in iter_ready_repeaters():
                metrics_counter("commcare.repeaters.check.attempt_forward")
                process_repeater.delay(repeater.domain, repeater.repeater_id)

                if datetime.utcnow() > twentythree_hours_later:
                    # Break after process_repeater() to avoid a stale lock
                    break
    finally:
        check_repeater_lock.release()


def iter_ready_repeaters():
    """
    Cycles through repeaters (repeatedly ;) ) until there are no more
    repeat records ready to be sent.
    """
    while True:
        yielded = False
        for repeater in Repeater.objects.all_ready():
            if not repeater.domain_can_forward:
                continue

            if rate_limit_repeater(repeater.domain):
                repeater.rate_limit()
                continue

            yielded = True
            yield repeater

        if not yielded:
            # No repeaters are ready, or they are rate limited, or their
            # domains can't forward or are paused.
            return


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeater(domain, repeater_id):

    def is_retry(repeat_record):
        return repeat_record.state == State.Fail

    lock_key = f'process_repeater_{repeater_id}'
    repeater_lock = get_redis_lock(lock_key, timeout=23 * 60 * 60, name=lock_key)
    if not repeater_lock.acquire(blocking=False):
        return

    try:
        repeater = Repeater.objects.get(domain=domain, id=repeater_id)
        repeat_records = repeater.repeat_records_ready[:repeater.num_workers]
        header_tasks = [
            retry_process_repeat_record.s(rr.id, rr.domain)
            if is_retry(rr)
            else process_repeat_record.s(rr.id, rr.domain)
            for rr in repeat_records
        ]
        chord(header_tasks)(update_repeater.s(repeater.repeater_id))

    finally:
        repeater_lock.release()


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def update_repeater(repeat_record_states, repeater_id):
    """
    Determines whether the repeater should back off, based on the
    results of `fire_repeat_record()` tasks.
    """
    repeater = Repeater.objects.get(id=repeater_id)
    if any(s == State.Success for s in repeat_record_states):
        # At least one repeat record was sent successfully.
        repeater.reset_backoff()
    elif all(s in (State.Empty, None) for s in repeat_record_states):
        # Nothing was sent. Don't update the repeater.
        pass
    else:
        # All sent payloads failed.
        repeater.set_backoff()


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeat_record(repeat_record_id, domain):
    """
    NOTE: Keep separate from retry_process_repeat_record for monitoring purposes
    Domain is present here for domain tagging in datadog
    """
    return _process_repeat_record(RepeatRecord.objects.get(id=repeat_record_id))


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def retry_process_repeat_record(repeat_record_id, domain):
    """
    NOTE: Keep separate from process_repeat_record for monitoring purposes
    Domain is present here for domain tagging in datadog
    """
    return _process_repeat_record(RepeatRecord.objects.get(id=repeat_record_id))


def _process_repeat_record(repeat_record):
    state_or_none = None
    try:
        with TimingContext() as timer:
            state_or_none = repeat_record.fire()
        # round up to the nearest millisecond, meaning always at least 1ms
        report_repeater_usage(repeat_record.domain, milliseconds=int(timer.duration * 1000) + 1)
    except Exception:
        logging.exception('Failed to process repeat record: {}'.format(repeat_record.id))
    return state_or_none


metrics_gauge_task(
    'commcare.repeaters.overdue',
    RepeatRecord.objects.count_overdue,
    run_every=crontab(),  # every minute
    multiprocess_mode=MPM_MAX
)
