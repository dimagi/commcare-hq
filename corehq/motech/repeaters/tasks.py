from datetime import datetime, timedelta

from django.conf import settings

from celery.schedules import crontab
from celery.task import periodic_task, task
from celery.utils.log import get_task_logger

from dimagi.utils.couch import CriticalSection, get_redis_lock
from dimagi.utils.couch.undo import DELETED_SUFFIX

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
    MAX_RETRY_WAIT,
    RECORD_CANCELLED_STATE,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
    RECORD_SUCCESS_STATE,
    RECORDS_AT_A_TIME,
)
from .dbaccessors import (
    get_overdue_repeat_record_count,
    iterate_repeat_records,
)
from .models import (
    RepeaterStub,
    RepeatRecord,
    RepeatRecordAttempt,
    SQLRepeatRecord,
    domain_can_forward,
    get_payload,
    has_failed,
    is_queued,
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
    Delete RequestLogs older than 90 days.
    """
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
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

    # Long timeout to allow all waiting repeat records to be iterated
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
            for record in iterate_repeat_records(start, chunk_size=5000):
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


@task(serializer='pickle', queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeat_record(repeat_record):
    _process_repeat_record(repeat_record)


@task(serializer='pickle', queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def retry_process_repeat_record(repeat_record):
    _process_repeat_record(repeat_record)


def _process_repeat_record(repeat_record):

    # A RepeatRecord should ideally never get into this state, as the
    # domain_has_privilege check is also triggered in the create_repeat_records
    # in signals.py. But if it gets here, forcefully cancel the RepeatRecord.
    if not domain_can_forward(repeat_record.domain):
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
        if repeater.doc_type.endswith(DELETED_SUFFIX):
            if not repeat_record.doc_type.endswith(DELETED_SUFFIX):
                repeat_record.doc_type += DELETED_SUFFIX
                repeat_record.save()
        elif repeater.paused:
            # postpone repeat record by MAX_RETRY_WAIT so that these don't get picked in each cycle and
            # thus clogging the queue with repeat records with paused repeater
            repeat_record.postpone_by(MAX_RETRY_WAIT)
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


@task(serializer='pickle', queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeater_stub(repeater_stub: RepeaterStub):
    """
    Worker task to send SQLRepeatRecords in chronological order.

    This function assumes that ``repeater_stub`` checks have already
    been performed. Call via ``models.attempt_forward_now()``.
    """
    with CriticalSection(
        [f'process-repeater-{repeater_stub.repeater_id}'],
        fail_hard=False, block=False, timeout=5 * 60 * 60,
    ):
        for repeat_record in repeater_stub.repeat_records_ready[:RECORDS_AT_A_TIME]:
            try:
                payload = get_payload(repeater_stub.repeater, repeat_record)
            except Exception:
                # The repeat record is cancelled if there is an error
                # getting the payload. We can safely move to the next one.
                continue
            should_retry = not send_request(repeater_stub.repeater,
                                            repeat_record, payload)
            if should_retry:
                break


@task(serializer='pickle', queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def migrate_repeat_record(
    repeater_stub: RepeaterStub,
    couch_record: RepeatRecord,
):
    assert repeater_stub.domain == couch_record.domain
    sql_record = repeater_stub.repeat_records.create(
        domain=couch_record.domain,
        couch_id=couch_record.record_id,
        payload_id=couch_record.payload_id,
        state=couch_record.state,
        registered_at=couch_record.registered_on,
    )
    for attempt in couch_record.attempts:
        sql_record.sqlrepeatrecordattempt_set.create(
            state=attempt.state,
            message=attempt.message,
            created_at=attempt.datetime,
        )

    couch_record.migrated = True
    couch_record.next_check = None
    try:
        couch_record.save()
    except:  # noqa: E722
        logging.exception('Failed to migrate repeat record: '
                          f'{couch_record.record_id}')
        sql_record.delete()


@task(serializer='pickle', queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def revert_migrated(couch_record):
    """
    Unset the RepeatRecord "migrated" state, and set ``next_check`` for
    RepeatRecords that need to be sent.

    Used by the ``roll_back_record_migration`` management command.
    """
    couch_record.migrated = False
    if is_queued(couch_record):
        couch_record.next_check = datetime.utcnow()
    try:
        couch_record.save()
    except:  # noqa: E722
        logging.exception('Failed to revert migration for record: '
                          f'{couch_record.record_id}')


@task(serializer='pickle', queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def migrate_to_couch(sql_record: SQLRepeatRecord):
    """
    Create a Couch RepeatRecord for a new SQLRepeatRecord.

    Used by the ``roll_back_record_migration`` management command.
    """
    repeater_type = sql_record.repeater_stub.repeater.__class__.__name__
    couch_record = RepeatRecord(
        domain=sql_record.domain,
        repeater_id=sql_record.repeater_stub.repeater_id,
        repeater_type=repeater_type,
        payload_id=sql_record.payload_id,
        registered_on=sql_record.registered_at,
        next_check=datetime.utcnow() if is_queued(sql_record) else None,

        succeeded=sql_record.state == RECORD_SUCCESS_STATE,
        cancelled=sql_record.state == RECORD_CANCELLED_STATE,
        failure_reason=sql_record.failure_reason,

        overall_tries=sql_record.num_attempts,
        attempts=[RepeatRecordAttempt(
            succeeded=a.state == RECORD_SUCCESS_STATE,
            cancelled=a.state == RECORD_CANCELLED_STATE,
            datetime=a.created_at,
            failure_reason=a.message if has_failed(a) else '',
            success_response=a.message if not has_failed(a) else '',
        ) for a in sql_record.attempts],
    )
    couch_record.save()
    # Set `couch_id` so that running the roll_back_record_migration
    # command more than once will not migrate `sql_record` again.
    sql_record.couch_id = couch_record.record_id  # Idempotent
    sql_record.save()
