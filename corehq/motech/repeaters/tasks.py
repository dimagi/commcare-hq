import random
from datetime import datetime, timedelta

from django.conf import settings

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
    MAX_RETRY_WAIT,
    RATE_LIMITER_DELAY_RANGE,
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
                if datetime.utcnow() > twentythree_hours_later:
                    break

                metrics_counter("commcare.repeaters.check.attempt_forward")
                process_repeater.delay(repeater.domain, repeater.repeater_id)
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
    ...


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


def _process_repeat_record(repeat_record):
    # TODO: Will be unnecessary
    if repeat_record.state == State.Cancelled:
        return

    # TODO: Will be unnecessary
    if not domain_can_forward(repeat_record.domain) or repeat_record.exceeded_max_retries:
        # When creating repeat records, we check if a domain can forward so
        # we should never have a repeat record associated with a domain that
        # cannot forward, but this is just to be sure
        repeat_record.cancel()
        repeat_record.save()
        return

    # TODO: Will be unnecessary
    if repeat_record.repeater.is_deleted:
        repeat_record.cancel()
        repeat_record.save()
        return

    try:
        # TODO: Will be unnecessary
        if repeat_record.repeater.is_paused or toggles.PAUSE_DATA_FORWARDING.enabled(repeat_record.domain):
            # postpone repeat record by MAX_RETRY_WAIT so that it is not fetched
            # in the next check to process repeat records, which helps to avoid
            # clogging the queue
            repeat_record.postpone_by(MAX_RETRY_WAIT)

        # TODO: Will be unnecessary
        elif rate_limit_repeater(repeat_record.domain):
            # Spread retries evenly over the range defined by RATE_LIMITER_DELAY_RANGE
            # with the intent of avoiding clumping and spreading load
            repeat_record.postpone_by(random.uniform(*RATE_LIMITER_DELAY_RANGE))

        elif repeat_record.is_queued():
            # TODO: This is all
            with TimingContext() as timer:
                repeat_record.fire()
            # round up to the nearest millisecond, meaning always at least 1ms
            report_repeater_usage(repeat_record.domain, milliseconds=int(timer.duration * 1000) + 1)
    except Exception:
        logging.exception('Failed to process repeat record: {}'.format(repeat_record.id))


metrics_gauge_task(
    'commcare.repeaters.overdue',
    RepeatRecord.objects.count_overdue,
    run_every=crontab(),  # every minute
    multiprocess_mode=MPM_MAX
)
