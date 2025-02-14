"""
check_repeaters() and process_repeaters()
=========================================

check_repeaters()
-----------------

The ``check_repeaters()`` task is how repeat records are sent, and its
workflow was shaped by the fact that repeaters and repeat records were
stored in CouchDB.

``check_repeaters()`` iterates all **repeat records** where the value of
``RepeatRecord.next_check`` is in the past.

We iterate them in parallel by dividing them into partitions (four
partitions in production). Repeat records are partitioned using their
ID. (``partition = RepeatRecord.id % num_partitions``.)

For each repeat record, ``check_repeaters_in_partition()`` calls
``RepeatRecord.attempt_forward_now()``. Execution ends up back in the
``tasks`` module when ``RepeatRecord.attempt_forward_now()`` calls
``_process_repeat_record()``. It runs a battery of checks, and if they
all succeed, ``RepeatRecord.fire()`` is called.

This process has several disadvantages:

* It iterates many repeat records that will not be sent. It has no way
  to filter out the repeat records of paused or deleted repeaters.

* It attempts to forward all the repeat records of a repeater, even if
  every previous repeat record has failed.

* We don't have a way to send repeat records in chronological order.

* Controlling the rate at which repeat records are sent is difficult.
  (e.g. Currently we use a separate queue to reduce the rate of sending
  the payloads of data source repeaters.)


process_repeaters()
-------------------

The ``process_repeaters()`` task sends repeat records, but does so in a
way that takes advantage of foreign keys between repeaters and their
repeat records.

This process is enabled using the ``PROCESS_REPEATERS`` feature flag.

The ``iter_ready_repeater_ids()`` generator yields the IDs of repeaters
that have repeat records ready to be sent. It does so in a round-robin
fashion, cycling through their domains. It does this so that:

* Domains and repeaters are not rate-limited unnecessarily.
* CommCare HQ tries to avoid flooding remote APIs by distributing the
  load among all active repeaters.
* No domain has to wait while another domain consumes all the repeat
  record queue workers.

``process_repeaters()`` creates a group of Celery tasks where each task
is a Celery chord for one repeater. The chord sends the next batch of
the repeater's repeat records, and then updates the repeater with the
results of those send attempts. The batch size defaults to 7, and can
be configured per repeater. Setting the batch size to 1 will send
repeat records in chronological order. If the remote endpoint is
offline or consistently returns errors, then the repeater will be
updated to back off. If any send attempts succeeded and a backoff had
been set, then the backoff is reset.

``process_repeaters()`` runs the group of tasks in parallel. When they
have completed, ``process_repeaters()`` loops through the repeaters
again, until there are no more repeat records ready to be sent.

"""
import random
import time
import uuid
from datetime import datetime, timedelta
from inspect import cleandoc

from django.conf import settings

from celery import chord
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from django_redis import get_redis_connection

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

    def endpoint_duration(timer_):
        return next((
            sub.duration
            for sub in timer_.to_list(exclude_root=True)
            if sub.name == ENDPOINT_TIMER
        ), None)  # If there was a payload error, we won't have sent to an endpoint

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
                request_duration = endpoint_duration(timer)
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
    process_repeaters_lock = get_redis_lock(
        PROCESS_REPEATERS_KEY,
        timeout=None,  # Iterating repeaters forever is fine
        name=PROCESS_REPEATERS_KEY,
    )
    if not process_repeaters_lock.acquire(blocking=False):
        return

    metrics_counter('commcare.repeaters.process_repeaters.start')
    try:
        group = 0
        redis = get_redis_connection()
        timeout_ms = 30 * 60 * 1000  # half an hour
        redis.set(f'repeater_group_{group}', 0, px=timeout_ms)
        while True:
            metrics_counter('commcare.repeaters.process_repeaters.iter_once')
            # A filtered list of the repeater IDs originally returned by
            # `Repeater.objects.get_all_ready_ids_by_domain()`:
            repeater_ids = list(iter_filtered_repeater_ids())
            if not repeater_ids:
                return
            for repeater_id in repeater_ids:
                lock = RepeaterLock(repeater_id)
                if lock.acquire():  # non-blocking
                    process_repeater(repeater_id, lock.token, group)

            while int(redis.get(f'repeater_group_{group}')) == 0:
                # Wait for (at least) one `process_repeater` task to finish
                # so that `Repeater.objects.get_all_ready_ids_by_domain()`
                # will return an updated set of repeaters. (This `while`
                # loop mimics redis-py's `Lock.acquire(blocking=True)`.)
                # https://github.com/redis/redis-py/blob/e0906519/redis/lock.py#L209-L218
                time.sleep(0.1)
            group += 1
    finally:
        process_repeaters_lock.release()
        metrics_counter('commcare.repeaters.process_repeaters.complete')


def iter_filtered_repeater_ids():
    """
    Filters ready repeater_ids based on whether data forwarding is
    enabled for the domain, and rate limiting.
    """
    for domain, repeater_id in iter_ready_domain_repeater_ids():
        if not domain_can_forward_now(domain):
            continue
        if rate_limit_repeater(domain, repeater_id):
            continue
        yield repeater_id


def iter_ready_domain_repeater_ids():
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


def process_repeater(repeater_id, lock_token, group):
    """
    Initiates a Celery chord to process a repeater.
    """

    def get_task_signature(repeat_record):
        task_ = {
            State.Pending: process_pending_repeat_record,
            State.Fail: process_failed_repeat_record,
        }[repeat_record.state]
        return task_.s(repeat_record.id, repeat_record.domain)

    repeater = Repeater.objects.get(id=repeater_id)
    repeat_records = repeater.repeat_records_ready[:repeater.num_workers]
    header_tasks = [get_task_signature(rr) for rr in repeat_records]
    callback = update_repeater.s(repeater_id, lock_token, group)
    chord(header_tasks, callback)()


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
    The duration since ``repeat_record`` was registered or last attempted.

    Buckets are exponential: [1m, 6m, 36m, 3.6h, 21.6h, 5.4d]
    """
    buckets = [60 * (6 ** exp) for exp in range(6)]
    metrics_histogram(
        'commcare.repeaters.process_repeaters.repeat_record_wait',
        _get_wait_duration_seconds(repeat_record),
        bucket_tag='duration',
        buckets=buckets,
        bucket_unit='s',
        tags={'domain': repeat_record.domain},
        documentation=cleandoc(_metrics_wait_duration.__doc__)
    )


def _get_wait_duration_seconds(repeat_record):
    last_attempt = repeat_record.attempt_set.last()
    if last_attempt:
        duration_start = last_attempt.created_at
    else:
        duration_start = repeat_record.registered_at
    wait_duration = datetime.utcnow() - duration_start
    return int(wait_duration.total_seconds())


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def update_repeater(repeat_record_states, repeater_id, lock_token, group):
    """
    Determines whether the repeater should back off, based on the
    results of ``process_ready_repeat_record()``.

    ``group`` is the group number of the repeater. It is used to
    determine when (at least) one repeater in the group has been
    processed.
    """
    repeater = Repeater.objects.get(id=repeater_id)
    try:
        if all(s in (State.Empty, None) for s in repeat_record_states):
            # We can't tell anything about the remote endpoint.
            return
        success_or_invalid = (State.Success, State.InvalidPayload)
        if any(s in success_or_invalid for s in repeat_record_states):
            # The remote endpoint appears to be healthy.
            repeater.reset_backoff()
        else:
            # All the payloads that were sent failed. Try again later.
            metrics_counter(
                'commcare.repeaters.process_repeaters.repeater_backoff',
                tags={'domain': repeater.domain},
            )
            repeater.set_backoff()
    finally:
        lock = RepeaterLock(repeater_id, lock_token)
        lock.release()
        redis = get_redis_connection()
        redis.incr(f'repeater_group_{group}')


class RepeaterLock:
    """
    A utility class for encapsulating lock-related logic for a repeater.
    """

    timeout = 30 * 60  # Half an hour

    def __init__(self, repeater_id, lock_token=None):
        self.token = lock_token
        self._lock = self._get_lock(repeater_id)

    def acquire(self):
        assert self.token is None, 'You have already acquired this lock'
        # Generate a lock token using `uuid1()` the same way that
        # `redis.lock.Lock` does. The `Lock` class uses the token to
        # determine ownership, so that one process can acquire a
        # lock and a different process can release it. This lock
        # will be released by the `update_repeater()` task.
        self.token = uuid.uuid1().hex
        return self._lock.acquire(blocking=False, token=self.token)

    def reacquire(self):
        assert self.token, 'Missing lock token'
        # Reset the lock timeout
        # https://github.com/redis/redis-py/blob/ff120df78ccd85d6e2e2938ee02d1eb831676724/redis/lock.py#L235
        return self._lock.reacquire()

    def release(self):
        assert self.token, 'Missing lock token'
        return self._lock.release()

    def _get_lock(self, repeater_id):
        name = f'process_repeater_{repeater_id}'
        lock = get_redis_lock(key=name, name=name, timeout=self.timeout)
        if self.token:
            lock.local.token = self.token
        return lock


metrics_gauge_task(
    'commcare.repeaters.overdue',
    RepeatRecord.objects.count_overdue,
    run_every=crontab(),  # every minute
    multiprocess_mode=MPM_MAX
)


# This metric monitors the number of RepeatRecords ready to be sent. An
# unexpected increase indicates a problem with `process_repeaters()`.
metrics_gauge_task(
    'commcare.repeaters.process_repeaters.count_all_ready',
    RepeatRecord.objects.count_all_ready,
    run_every=crontab(minute='*/5'),  # every five minutes
    multiprocess_mode=MPM_MAX
)
