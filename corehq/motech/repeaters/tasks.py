from contextlib import contextmanager
from datetime import datetime, timedelta

from django.conf import settings

from celery.schedules import crontab
from celery.utils.log import get_task_logger

from dimagi.utils.couch import CriticalSection, get_redis_lock
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.apps.celery import periodic_task, task
from corehq.motech.models import RequestLog
from corehq.util.metrics import (
    make_buckets_from_timedeltas,
    metrics_counter,
    metrics_gauge_task,
    metrics_histogram_timer,
)
from corehq.util.metrics.const import MPM_MAX
from corehq.util.soft_assert import soft_assert

from .const import (
    CHECK_REPEATERS_INTERVAL,
    CHECK_REPEATERS_KEY,
    CHECK_REPEATERS_PARTITION_COUNT,
    MAX_RETRY_WAIT,
    RECORDS_AT_A_TIME,
    State,
)
from .models import (
    Repeater,
    SQLRepeatRecord,
    domain_can_forward,
    get_payload,
    is_sql_id,
    send_request,
)

_check_repeaters_buckets = make_buckets_from_timedeltas(
    timedelta(seconds=10),
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(hours=1),
    timedelta(hours=5),
    timedelta(hours=10),
)
MOTECH_DEV = '@'.join(('nhooper', 'dimagi.com'))
_soft_assert = soft_assert(to=MOTECH_DEV)
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
            for record in SQLRepeatRecord.objects.iter_partition(
                    start, partition, CHECK_REPEATERS_PARTITION_COUNT):
                if not _soft_assert(
                    datetime.utcnow() < twentythree_hours_later,
                    "I've been iterating repeat records for 23 hours. I quit!"
                ):
                    break

                metrics_counter("commcare.repeaters.check.attempt_forward")
                record.attempt_forward_now(is_retry=True)
            else:
                iterating_time = datetime.utcnow() - start
                _soft_assert(
                    iterating_time < timedelta(hours=6),
                    f"It took {iterating_time} to iterate repeat records."
                )
    finally:
        check_repeater_lock.release()


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeat_record(repeat_record_id, domain):
    """
    NOTE: Keep separate from retry_process_repeat_record for monitoring purposes
    Domain is present here for domain tagging in datadog
    """
    repeat_record = _get_repeat_record(repeat_record_id)
    _process_repeat_record(repeat_record)


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def retry_process_repeat_record(repeat_record_id, domain):
    """
    NOTE: Keep separate from process_repeat_record for monitoring purposes
    Domain is present here for domain tagging in datadog
    """
    repeat_record = _get_repeat_record(repeat_record_id)
    _process_repeat_record(repeat_record)


def _get_repeat_record(repeat_record_id):
    if not is_sql_id(repeat_record_id):
        # can be removed after all in-flight tasks with Couch ids have been processed
        return SQLRepeatRecord.objects.get(couch_id=repeat_record_id)
    return SQLRepeatRecord.objects.get(id=repeat_record_id)


def _process_repeat_record(repeat_record):
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
        with _delete_couch_record(repeat_record):
            repeat_record.save()
        return

    try:
        if repeat_record.repeater.is_paused:
            # postpone repeat record by MAX_RETRY_WAIT so that it is not fetched
            # in the next check to process repeat records, which helps to avoid
            # clogging the queue
            repeat_record.postpone_by(MAX_RETRY_WAIT)
        elif repeat_record.is_queued():
            repeat_record.fire()
    except Exception:
        logging.exception('Failed to process repeat record: {}'.format(repeat_record.id))


@contextmanager
def _delete_couch_record(repeat_record):
    from django.db.models import Model

    def delete(_, couch_object):
        if not couch_object.doc_type.endswith(DELETED_SUFFIX):
            couch_object.doc_type += DELETED_SUFFIX

    if isinstance(repeat_record, Model):
        assert not repeat_record._migration_get_custom_sql_to_couch_functions()
        repeat_record._migration_get_custom_sql_to_couch_functions = lambda: [delete]
        try:
            yield
        finally:
            del repeat_record._migration_get_custom_sql_to_couch_functions
            assert not repeat_record._migration_get_custom_sql_to_couch_functions()
    else:
        delete(..., repeat_record)
        yield


metrics_gauge_task(
    'commcare.repeaters.overdue',
    SQLRepeatRecord.objects.count_overdue,
    run_every=crontab(),  # every minute
    multiprocess_mode=MPM_MAX
)


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeater(repeater_id):
    """
    Worker task to send SQLRepeatRecords in chronological order.

    This function assumes that ``repeater`` checks have already
    been performed. Call via ``models.attempt_forward_now()``.
    """
    repeater = Repeater.objects.get(id=repeater_id)
    with CriticalSection(
        [f'process-repeater-{repeater.repeater_id}'],
        fail_hard=False, block=False, timeout=5 * 60 * 60,
    ):
        for repeat_record in repeater.repeat_records_ready[:RECORDS_AT_A_TIME]:
            try:
                payload = get_payload(repeater, repeat_record)
            except Exception:
                # The repeat record is cancelled if there is an error
                # getting the payload. We can safely move to the next one.
                continue
            should_retry = not send_request(repeater,
                                            repeat_record, payload)
            if should_retry:
                break
