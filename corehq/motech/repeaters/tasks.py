import uuid
from datetime import datetime, timedelta

from django.conf import settings

from celery import chord
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from django_redis import get_redis_connection
from redis.lock import Lock

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
from corehq.util.metrics.lockmeter import MeteredLock
from corehq.util.timer import TimingContext

from .const import (
    CHECK_REPEATERS_INTERVAL,
    CHECK_REPEATERS_KEY,
    ENDPOINT_TIMER,
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
            for domain, repeater_id, lock_token in iter_ready_repeater_ids_forever():
                if datetime.utcnow() > twentythree_hours_later:
                    break

                metrics_counter("commcare.repeaters.check.attempt_forward")
                process_repeater.delay(domain, repeater_id, lock_token)
    finally:
        check_repeater_lock.release()


def iter_ready_repeater_ids_forever():
    """
    Cycles through repeaters (repeatedly ;) ) until there are no more
    repeat records ready to be sent.
    """
    while True:
        yielded = False
        with metrics_histogram_timer(
            "commcare.repeaters.check.each_repeater",
            timing_buckets=_check_repeaters_buckets,
        ):
            for domain, repeater_id in _iter_ready_repeater_ids_once():
                lock = get_repeater_lock(repeater_id)
                lock_token = uuid.uuid1().hex  # The same way Lock does it
                if lock.acquire(blocking=False, token=lock_token):
                    yielded = True
                    yield domain, repeater_id, lock_token

        if not yielded:
            # No repeaters are ready
            return


def get_repeater_lock(repeater_id):
    redis = get_redis_connection()
    name = f'process_repeater_{repeater_id}'
    one_day = 24 * 60 * 60
    lock = Lock(redis, name, timeout=one_day)
    return MeteredLock(lock, name)


def _iter_ready_repeater_ids_once():
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

    def iter_domain_repeaters(dom):
        try:
            rep_id = repeater_ids_by_domain[dom].pop(0)
        except IndexError:
            return
        else:
            yield rep_id

    repeater_ids_by_domain = Repeater.objects.get_all_ready_ids_by_domain()
    while True:
        if not repeater_ids_by_domain:
            return
        for domain in list(repeater_ids_by_domain.keys()):
            try:
                repeater_id = next(iter_domain_repeaters(domain))
            except StopIteration:
                # We've exhausted the repeaters for this domain
                del repeater_ids_by_domain[domain]
                continue
            else:
                if rate_limit_repeater(domain):
                    continue  # Skip this repeater
                yield domain, repeater_id


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeater(domain, repeater_id, lock_token):

    def get_task_signature(repeat_record):
        task = {
            State.Pending: process_pending_repeat_record,
            State.Fail: process_failed_repeat_record,
        }[repeat_record.state]
        return task.s(repeat_record.id, repeat_record.domain)

    repeater = Repeater.objects.get(domain=domain, id=repeater_id)
    repeat_records = repeater.repeat_records_ready[:repeater.num_workers]
    header_tasks = [get_task_signature(rr) for rr in repeat_records]
    chord(header_tasks)(update_repeater.s(repeater_id, lock_token))


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_pending_repeat_record(repeat_record_id, domain):
    # NOTE: Keep separate from `process_failed_repeat_record()` for
    # monitoring purposes. `domain` is for tagging in Datadog
    return _process_repeat_record(repeat_record_id)


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_failed_repeat_record(repeat_record_id, domain):
    # NOTE: Keep separate from `process_pending_repeat_record()` for
    # monitoring purposes. `domain` is for tagging in Datadog
    return _process_repeat_record(repeat_record_id)


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
            # _process_repeat_record() can return None if it is called
            # with a repeat record whose state is Success or Empty. That
            # can't happen in this workflow, but None is included for
            # completeness.
            pass
        else:
            # All sent payloads failed. Try again later.
            repeater.set_backoff()
    finally:
        lock = get_repeater_lock(repeater_id)
        lock.local.token = lock_token
        lock.release()


def _process_repeat_record(repeat_record_id):
    state_or_none = None
    with TimingContext('process_repeat_record') as timer:
        try:
            repeat_record = (
                RepeatRecord.objects
                .prefetch_related('repeater', 'attempt_set')
                .get(id=repeat_record_id)
            )
            report_repeater_attempt(repeat_record.domain)
            if not _is_repeat_record_ready(repeat_record):
                return None
            with timer('fire_timing') as fire_timer:
                state_or_none = repeat_record.fire(timing_context=fire_timer)
            # round up to the nearest millisecond, meaning always at least 1ms
            report_repeater_usage(repeat_record.domain, milliseconds=int(fire_timer.duration * 1000) + 1)
            action = 'attempted'
            request_duration = [
                sub.duration for sub in fire_timer.to_list(exclude_root=True) if sub.name == ENDPOINT_TIMER
            ][0]
        except Exception:
            logging.exception('Failed to process repeat record: {}'.format(repeat_record.id))
            return state_or_none

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
    return state_or_none


def _is_repeat_record_ready(repeat_record):
    # Fail loudly if repeat_record is not ready. _process_repeat_record()
    # will log an exception.
    assert repeat_record.state in (State.Pending, State.Fail)

    # The repeater could have been paused while it was being processed
    return (
        not repeat_record.repeater.is_paused
        and not toggles.PAUSE_DATA_FORWARDING.enabled(repeat_record.domain)
        and not rate_limit_repeater(repeat_record.domain)
    )


metrics_gauge_task(
    'commcare.repeaters.overdue',
    RepeatRecord.objects.count_overdue,
    run_every=crontab(minute='*/5'),  # Every 5 minutes
    multiprocess_mode=MPM_MAX
)
