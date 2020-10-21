from datetime import datetime, timedelta

from django.conf import settings

from celery.schedules import crontab
from celery.task import periodic_task, task
from celery.utils.log import get_task_logger

from dimagi.utils.chunked import chunked
from dimagi.utils.couch import get_redis_lock
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.motech.models import RequestLog
from corehq.motech.repeaters.const import (
    CHECK_REPEATERS_INTERVAL,
    CHECK_REPEATERS_PARTITION_COUNT,
    CHECK_REPEATERS_KEY,
    MAX_RETRY_WAIT,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
)
from corehq.motech.repeaters.dbaccessors import (
    get_overdue_repeat_record_count,
    iterate_repeat_record_ids,
    iterate_repeat_records_for_ids,
)
from corehq.privileges import DATA_FORWARDING, ZAPIER_INTEGRATION
from corehq.util.metrics import (
    make_buckets_from_timedeltas,
    metrics_counter,
    metrics_gauge_task,
    metrics_histogram_timer,
)
from corehq.util.metrics.const import MPM_MAX
from corehq.util.soft_assert import soft_assert

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


@periodic_task(
    run_every=crontab(day_of_month=27),
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def clean_logs():
    """
    Drop MOTECH logs older than 90 days.

    Runs on the 27th of every month.
    """
    ninety_days_ago = datetime.now() - timedelta(days=90)
    RequestLog.objects.filter(timestamp__lt=ninety_days_ago).delete()


@periodic_task(
    run_every=CHECK_REPEATERS_INTERVAL,
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def check_repeaters():
    # this creates a task for all partitions
    # the Nth child task determines if a lock is available for the Nth partition
    for current_partition in range(CHECK_REPEATERS_PARTITION_COUNT):
        check_repeaters_in_partition.delay(current_partition, CHECK_REPEATERS_PARTITION_COUNT)


def _iterate_record_ids_for_partition(start, partition, total_partitions):
    for record_id in iterate_repeat_record_ids(start, chunk_size=100000):
        if hash(record_id) % total_partitions == partition:
            yield record_id


def _iterate_repeat_records_for_partition(start, partition, total_partitions):
    # chunk the fetching of documents from couch
    for chunked_ids in chunked(_iterate_record_ids_for_partition(start, partition, total_partitions), 10000):
        yield from iterate_repeat_records_for_ids(chunked_ids)


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def check_repeaters_in_partition(partition, total_partitions):
    start = datetime.utcnow()
    twentythree_hours_sec = 23 * 60 * 60
    twentythree_hours_later = start + timedelta(hours=23)

    # Long timeout to allow all waiting repeat records to be iterated
    lock_key = f"{CHECK_REPEATERS_KEY}_{partition}_in_{total_partitions}"
    check_repeater_lock = get_redis_lock(
        lock_key,
        timeout=twentythree_hours_sec,
        name=lock_key,
    )
    if not check_repeater_lock.acquire(blocking=False):
        metrics_counter("commcare.repeaters.check.locked_out")
        return

    try:
        with metrics_histogram_timer(
            "commcare.repeaters.check.processing",
            timing_buckets=_check_repeaters_buckets,
        ):
            for record in _iterate_repeat_records_for_partition(start, partition, total_partitions):
                if not _soft_assert(
                    datetime.utcnow() < twentythree_hours_later,
                    "I've been iterating repeat records for 23 hours. I quit!"
                ):
                    break

                metrics_counter("commcare.repeaters.check.attempt_forward")
                record.attempt_forward_now()
            else:
                iterating_time = datetime.utcnow() - start
                _soft_assert(
                    iterating_time < timedelta(hours=6),
                    f"It took {iterating_time} to iterate repeat records."
                )
    finally:
        check_repeater_lock.release()


@task(serializer='pickle', queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeat_record(repeat_record):

    # A RepeatRecord should ideally never get into this state, as the
    # domain_has_privilege check is also triggered in the create_repeat_records
    # in signals.py. But if it gets here, forcefully cancel the RepeatRecord.
    # todo reconcile ZAPIER_INTEGRATION and DATA_FORWARDING
    #  they each do two separate things and are priced differently,
    #  but use the same infrastructure
    if not (domain_has_privilege(repeat_record.domain, ZAPIER_INTEGRATION)
            or domain_has_privilege(repeat_record.domain, DATA_FORWARDING)):
        repeat_record.cancel()
        repeat_record.save()

    if (
        repeat_record.state == RECORD_FAILURE_STATE and
        repeat_record.overall_tries >= repeat_record.max_possible_tries
    ):
        repeat_record.cancel()
        repeat_record.save()
        return
    if repeat_record.cancelled:
        return

    repeater = repeat_record.repeater
    if not repeater:
        repeat_record.cancel()
        repeat_record.save()
        return

    try:
        if repeater.paused:
            # postpone repeat record by 1 day so that these don't get picked in each cycle and
            # thus clogging the queue with repeat records with paused repeater
            repeat_record.postpone_by(MAX_RETRY_WAIT)
            return

        if repeater.doc_type.endswith(DELETED_SUFFIX):
            if not repeat_record.doc_type.endswith(DELETED_SUFFIX):
                repeat_record.doc_type += DELETED_SUFFIX
                repeat_record.save()
        elif repeat_record.state == RECORD_PENDING_STATE or repeat_record.state == RECORD_FAILURE_STATE:
                repeat_record.fire()
    except Exception:
        logging.exception('Failed to process repeat record: {}'.format(repeat_record._id))


repeaters_overdue = metrics_gauge_task(
    'commcare.repeaters.overdue',
    get_overdue_repeat_record_count,
    run_every=crontab(),  # every minute
    multiprocess_mode=MPM_MAX
)
