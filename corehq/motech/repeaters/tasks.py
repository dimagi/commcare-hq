import random
from datetime import datetime, timedelta

from django.conf import settings

from celery.schedules import crontab
from celery.utils.log import get_task_logger

from dimagi.utils.couch import get_redis_lock

from corehq import toggles
from corehq.apps.celery import periodic_task, task
from corehq.motech.models import RequestLog
from corehq.util.metrics import (
    make_buckets_from_timedeltas,
    metrics_counter,
    metrics_gauge_task,
    metrics_histogram,
    metrics_histogram_timer,
)
from corehq.util.metrics.const import MPM_MAX
from corehq.util.timer import TimingContext

from .const import (
    CHECK_REPEATERS_INTERVAL,
    CHECK_REPEATERS_KEY,
    CHECK_REPEATERS_PARTITION_COUNT,
    ENDPOINT_TIMER,
    MAX_RETRY_WAIT,
    RATE_LIMITER_DELAY_RANGE,
    State,
)
from .models import RepeatRecord, domain_can_forward

from ..rate_limiter import (
    rate_limit_repeater,
    report_repeater_attempt,
    report_repeater_usage,
)

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
    # this creates a task for all partitions
    # the Nth child task determines if a lock is available for the Nth partition
    for current_partition in range(CHECK_REPEATERS_PARTITION_COUNT):
        check_repeaters_in_partition.delay(current_partition)


@task(queue=settings.CELERY_PERIODIC_QUEUE)
def check_repeaters_in_partition(partition):
    """
    The CHECK_REPEATERS_PARTITION_COUNT constant dictates the total number of partitions
    :param partition: index of partition to check
    """
    start = datetime.utcnow()
    twentythree_hours_sec = 23 * 60 * 60
    twentythree_hours_later = start + timedelta(hours=23)

    # Long timeout to allow all waiting repeat records to be iterated
    lock_key = f"{CHECK_REPEATERS_KEY}_{partition}_in_{CHECK_REPEATERS_PARTITION_COUNT}"
    check_repeater_lock = get_redis_lock(
        lock_key,
        timeout=twentythree_hours_sec,
        name=lock_key,
    )
    if not check_repeater_lock.acquire(blocking=False):
        metrics_counter("commcare.repeaters.check.locked_out", tags={'partition': partition})
        return

    try:
        with metrics_histogram_timer(
            "commcare.repeaters.check.processing",
            timing_buckets=_check_repeaters_buckets,
        ):
            for record in RepeatRecord.objects.iter_partition(
                    start, partition, CHECK_REPEATERS_PARTITION_COUNT):

                if datetime.utcnow() > twentythree_hours_later:
                    break

                metrics_counter("commcare.repeaters.check.attempt_forward")
                record.attempt_forward_now(is_retry=True)
    finally:
        check_repeater_lock.release()


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeat_record(repeat_record_id, domain):
    """
    NOTE: Keep separate from retry_process_repeat_record for monitoring purposes
    Domain is present here for domain tagging in datadog
    """
    _process_repeat_record(RepeatRecord.objects.get(id=repeat_record_id))


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def retry_process_repeat_record(repeat_record_id, domain):
    """
    NOTE: Keep separate from process_repeat_record for monitoring purposes
    Domain is present here for domain tagging in datadog
    """
    _process_repeat_record(RepeatRecord.objects.get(id=repeat_record_id))


@task(queue=settings.CELERY_REPEAT_RECORD_DATASOURCE_QUEUE)
def process_datasource_repeat_record(repeat_record_id, domain):
    """
    NOTE: Keep separate from retry_process_datasource_repeat_record for monitoring purposes
    Domain is present here for domain tagging in datadog
    """
    _process_repeat_record(RepeatRecord.objects.get(id=repeat_record_id))


@task(queue=settings.CELERY_REPEAT_RECORD_DATASOURCE_QUEUE)
def retry_process_datasource_repeat_record(repeat_record_id, domain):
    """
    NOTE: Keep separate from process_datasource_repeat_record for monitoring purposes
    Domain is present here for domain tagging in datadog
    """
    _process_repeat_record(RepeatRecord.objects.get(id=repeat_record_id))


def _process_repeat_record(repeat_record):
    request_duration = action = None
    with TimingContext('process_repeat_record') as timer:
        if repeat_record.state == State.Cancelled:
            return

        if not domain_can_forward(repeat_record.domain) or repeat_record.exceeded_max_retries:
            # When creating repeat records, we check if a domain can forward so
            # we should never have a repeat record associated with a domain that
            # cannot forward, but this is just to be sure
            repeat_record.cancel()
            repeat_record.save()
            return

        if repeat_record.repeater.is_deleted:
            repeat_record.cancel()
            repeat_record.save()
            return

        try:
            if repeat_record.repeater.is_paused or toggles.PAUSE_DATA_FORWARDING.enabled(repeat_record.domain):
                # postpone repeat record by MAX_RETRY_WAIT so that it is not fetched
                # in the next check to process repeat records, which helps to avoid
                # clogging the queue
                repeat_record.postpone_by(MAX_RETRY_WAIT)
                action = 'paused'
            elif rate_limit_repeater(repeat_record.domain, repeat_record.repeater.repeater_id):
                # Spread retries evenly over the range defined by RATE_LIMITER_DELAY_RANGE
                # with the intent of avoiding clumping and spreading load
                repeat_record.postpone_by(random.uniform(*RATE_LIMITER_DELAY_RANGE))
                action = 'rate_limited'
            elif repeat_record.is_queued():
                report_repeater_attempt(repeat_record.repeater.repeater_id)
                with timer('fire_timing') as fire_timer:
                    repeat_record.fire(timing_context=fire_timer)
                # round up to the nearest millisecond, meaning always at least 1ms
                report_repeater_usage(repeat_record.domain, milliseconds=int(fire_timer.duration * 1000) + 1)
                action = 'attempted'
                request_duration = [
                    sub.duration for sub in fire_timer.to_list(exclude_root=True) if sub.name == ENDPOINT_TIMER
                ][0]
        except Exception:
            logging.exception('Failed to process repeat record: {}'.format(repeat_record.id))
            return

    if action:
        processing_time = timer.duration - request_duration if request_duration else timer.duration
        metrics_histogram(
            'commcare.repeaters.repeat_record_processing.timing',
            processing_time * 1000,
            buckets=(100, 500, 1000, 5000),
            bucket_tag='duration',
            bucket_unit='ms',
            tags={
                'domain': repeat_record.domain,
                'action': action,
            },
        )


metrics_gauge_task(
    'commcare.repeaters.overdue',
    RepeatRecord.objects.count_overdue,
    run_every=crontab(),  # every minute
    multiprocess_mode=MPM_MAX
)
