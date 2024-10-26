import random
import uuid
from datetime import datetime, timedelta, UTC

from django.conf import settings

from celery import chord
from celery.schedules import crontab
from celery.utils.log import get_task_logger

from dimagi.utils.couch import get_redis_lock

from corehq import toggles
from corehq.apps.celery import periodic_task, task
from corehq.motech.models import RequestLog
from corehq.motech.rate_limiter import (
    rate_limit_repeater,
    report_repeater_attempt,
    report_repeater_usage,
)
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
    PROCESS_REPEATERS_INTERVAL,
    PROCESS_REPEATERS_KEY,
    RATE_LIMITER_DELAY_RANGE,
    State,
)
from .models import (
    Repeater,
    RepeatRecord,
    domain_can_forward,
    domain_can_forward_now,
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


@periodic_task(
    run_every=PROCESS_REPEATERS_INTERVAL,
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def process_repeaters():
    """
    Processes repeaters, instead of processing repeat records
    independently the way that ``check_repeaters()`` does.
    """
    process_repeater_lock = get_redis_lock(
        PROCESS_REPEATERS_KEY,
        timeout=None,  # Iterating repeaters forever is fine
        name=PROCESS_REPEATERS_KEY,
    )
    # How to recover from a crash: If `process_repeaters()` needs to be
    # restarted and `process_repeater_lock` was not released, expire the
    # lock to allow `process_repeaters()` to start:
    #
    # >>> from dimagi.utils.couch.cache.cache_core import get_redis_client
    # >>> from corehq.motech.repeaters.const import PROCESS_REPEATERS_KEY
    # >>> client = get_redis_client()
    # >>> client.expire(PROCESS_REPEATERS_KEY, timeout=0)
    if not process_repeater_lock.acquire(blocking=False):
        return

    try:
        for domain, repeater_id, lock_token in iter_ready_repeater_ids_forever():
            process_repeater.delay(domain, repeater_id, lock_token)
    finally:
        process_repeater_lock.release()


def iter_ready_repeater_ids_forever():
    """
    Cycles through repeaters (repeatedly ;) ) until there are no more
    repeat records ready to be sent.
    """
    while True:
        yielded = False
        for domain, repeater_id in iter_ready_repeater_ids_once():
            if not domain_can_forward_now(domain):
                continue
            if rate_limit_repeater(domain, repeater_id):
                continue

            lock = get_repeater_lock(repeater_id)
            # Generate a lock token using `uuid1()` the same way that
            # `redis.lock.Lock` does. The `Lock` class uses the token to
            # determine ownership, so that one process can acquire a
            # lock and a different process can release it. This lock
            # will be released by the `update_repeater()` task.
            lock_token = uuid.uuid1().hex
            if lock.acquire(blocking=False, token=lock_token):
                yielded = True
                yield domain, repeater_id, lock_token

        if not yielded:
            # No repeaters are ready, or their domains can't forward or
            # are paused.
            return


def iter_ready_repeater_ids_once():
    """
    Yields domain-repeater_id tuples in a round-robin fashion.

    e.g. ::
        ('domain1', 'repeater_id1'),
        ('domain2', 'repeater_id2'),
        ('domain3', 'repeater_id3'),
        ('domain1', 'repeater_id4'),
        ('domain2', 'repeater_id5'),
        ...

    """
    repeater_ids_by_domain = get_repeater_ids_by_domain()
    while True:
        if not repeater_ids_by_domain:
            return
        for domain in list(repeater_ids_by_domain.keys()):
            try:
                repeater_id = repeater_ids_by_domain[domain].pop()
            except IndexError:
                # We've exhausted the repeaters for this domain
                del repeater_ids_by_domain[domain]
                continue
            yield domain, repeater_id


def get_repeater_lock(repeater_id):
    name = f'process_repeater_{repeater_id}'
    three_hours = 3 * 60 * 60
    return get_redis_lock(key=name, name=name, timeout=three_hours)


def get_repeater_ids_by_domain():
    repeater_ids_by_domain = Repeater.objects.get_all_ready_ids_by_domain()
    always_enabled_domains = set(toggles.PROCESS_REPEATERS.get_enabled_domains())
    return {
        domain: repeater_ids
        for domain, repeater_ids in repeater_ids_by_domain.items()
        if (
            domain in always_enabled_domains
            # FeatureRelease toggle: Check whether domain is randomly enabled
            or toggles.PROCESS_REPEATERS.enabled(domain, toggles.NAMESPACE_DOMAIN)
        )
    }


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeater(domain, repeater_id, lock_token):

    def get_task_signature(repeat_record):
        task_ = {
            State.Pending: process_pending_repeat_record,
            State.Fail: process_failed_repeat_record,
        }[repeat_record.state]
        return task_.s(repeat_record.id, repeat_record.domain)

    repeater = Repeater.objects.get(domain=domain, id=repeater_id)
    repeat_records = repeater.repeat_records_ready[:repeater.num_workers]
    header_tasks = [get_task_signature(rr) for rr in repeat_records]
    chord(header_tasks)(update_repeater.s(repeater_id, lock_token))


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_pending_repeat_record(repeat_record_id, domain):
    # NOTE: Keep separate from `process_failed_repeat_record()` for
    # monitoring purposes. `domain` is for tagging in Datadog
    return process_ready_repeat_record(repeat_record_id)


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_failed_repeat_record(repeat_record_id, domain):
    # NOTE: Keep separate from `process_pending_repeat_record()` for
    # monitoring purposes. `domain` is for tagging in Datadog
    return process_ready_repeat_record(repeat_record_id)


def process_ready_repeat_record(repeat_record_id):
    state_or_none = None
    with TimingContext('process_repeat_record') as timer:
        try:
            repeat_record = (
                RepeatRecord.objects
                .prefetch_related('repeater', 'attempt_set')
                .get(id=repeat_record_id)
            )
            if not is_repeat_record_ready(repeat_record):
                return None

            _metrics_wait_duration(repeat_record)
            report_repeater_attempt(repeat_record.repeater.repeater_id)
            with timer('fire_timing') as fire_timer:
                state_or_none = repeat_record.fire(timing_context=fire_timer)
            report_repeater_usage(
                repeat_record.domain,
                # round up to the nearest millisecond, meaning always at least 1ms
                milliseconds=int(fire_timer.duration * 1000) + 1
            )
        except Exception:
            logging.exception(f'Failed to process repeat record {repeat_record_id}')
    return state_or_none


def is_repeat_record_ready(repeat_record):
    # Fail loudly if repeat_record is not ready.
    # process_ready_repeat_record() will log an exception.
    assert repeat_record.state in (State.Pending, State.Fail)

    # The repeater could have been paused or rate-limited while it was
    # being processed
    return (
        not repeat_record.repeater.is_paused
        and domain_can_forward_now(repeat_record.domain)
        and not rate_limit_repeater(
            repeat_record.domain,
            repeat_record.repeater.repeater_id
        )
    )


def _metrics_wait_duration(repeat_record):
    """
    Metrics for the duration since ``repeat_record`` was registered or
    attempted.

    Max backoff for a Repeater (``MAX_RETRY_WAIT``) is 7 days.
    """
    if repeat_record.attempt_set:
        duration_start = repeat_record.attempt_set[-1].created_at
    else:
        duration_start = repeat_record.registered_at
    wait_duration = datetime.now(UTC) - duration_start
    buckets = [60 * (3 ** exp) for exp in range(10)]  # 1 minute to 9 days
    metrics_histogram(
        'commcare.repeaters.repeat_record.waited',
        wait_duration.total_seconds(),
        buckets=buckets,
        bucket_tag='duration',
        bucket_unit='s',
        tags={
            'domain': repeat_record.domain,
            'repeater': f'{repeat_record.domain}: {repeat_record.repeater.name}',
        },
    )


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def update_repeater(repeat_record_states, repeater_id, lock_token):
    """
    Determines whether the repeater should back off, based on the
    results of ``_process_repeat_record()`` tasks.
    """
    try:
        repeater = Repeater.objects.get(id=repeater_id)
        if any(s == State.Success for s in repeat_record_states):
            # At least one repeat record was sent successfully. The
            # remote endpoint is healthy.
            repeater.reset_backoff()
        elif all(s in (State.Empty, State.InvalidPayload, None)
                 for s in repeat_record_states):
            # We can't tell anything about the remote endpoint.
            # (_process_repeat_record() can return None on an exception.)
            pass
        else:
            # All sent payloads failed. Try again later.
            repeater.set_backoff()
    finally:
        lock = get_repeater_lock(repeater_id)
        lock.local.token = lock_token
        lock.release()


metrics_gauge_task(
    'commcare.repeaters.overdue',
    RepeatRecord.objects.count_overdue,
    run_every=crontab(),  # every minute
    multiprocess_mode=MPM_MAX
)


# This metric monitors the number of Repeaters with RepeatRecords ready to
# be sent. A steep increase indicates a problem with `process_repeaters()`.
metrics_gauge_task(
    'commcare.repeaters.all_ready',
    Repeater.objects.all_ready_count,
    run_every=crontab(minute='*/5'),  # every five minutes
    multiprocess_mode=MPM_MAX
)
