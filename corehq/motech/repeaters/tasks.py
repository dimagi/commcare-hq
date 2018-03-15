from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, timedelta
from celery.schedules import crontab
from couchdbkit import ResourceNotFound

from django.conf import settings
from celery.task import periodic_task, task
from celery.utils.log import get_task_logger
from redis.exceptions import LockError
from corehq.util.datadog.gauges import datadog_gauge_task
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.motech.repeaters.dbaccessors import iterate_repeat_records, \
    get_overdue_repeat_record_count
from corehq import toggles
from corehq.motech.repeaters.const import (
    CHECK_REPEATERS_INTERVAL,
    CHECK_REPEATERS_KEY,
    RECORD_PENDING_STATE,
    RECORD_FAILURE_STATE)

logging = get_task_logger(__name__)


@periodic_task(
    run_every=CHECK_REPEATERS_INTERVAL,
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def check_repeaters():
    start = datetime.utcnow()
    cutoff = start + CHECK_REPEATERS_INTERVAL

    redis_client = get_redis_client().client.get_client()

    # Timeout for slightly less than periodic check
    check_repeater_lock = redis_client.lock(
        CHECK_REPEATERS_KEY,
        timeout=CHECK_REPEATERS_INTERVAL.seconds - 10
    )
    if not check_repeater_lock.acquire(blocking=False):
        return

    for record in iterate_repeat_records(start):
        now = datetime.utcnow()
        lock_key = _get_repeat_record_lock_key(record)

        if now > cutoff:
            break

        lock = redis_client.lock(lock_key, timeout=60 * 60 * 48)
        if not lock.acquire(blocking=False):
            continue

        process_repeat_record.delay(record)

    try:
        check_repeater_lock.release()
    except LockError:
        # Ignore if already released
        pass


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeat_record(repeat_record):
    if repeat_record.state == RECORD_FAILURE_STATE and repeat_record.overall_tries >= repeat_record.max_possible_tries:
        repeat_record.cancel()
        repeat_record.save()
        return
    if repeat_record.cancelled:
        return

    try:
        repeat_record.repeater
    except ResourceNotFound:
        repeat_record.cancel()
        repeat_record.save()

    try:
        if repeat_record.repeater and repeat_record.repeater.paused:
            # postpone repeat record by 1 hour so that these don't get picked in each cycle and
            # thus clogging the queue with repeat records with paused repeater
            repeat_record.postpone_by(timedelta(hours=1))
            return
        if repeat_record.repeater.doc_type.endswith(DELETED_SUFFIX):
            if not repeat_record.doc_type.endswith(DELETED_SUFFIX):
                repeat_record.doc_type += DELETED_SUFFIX
                repeat_record.save()
        elif repeat_record.state == RECORD_PENDING_STATE or repeat_record.state == RECORD_FAILURE_STATE:
                repeat_record.fire()
    except Exception:
        logging.exception('Failed to process repeat record: {}'.format(repeat_record._id))


def _get_repeat_record_lock_key(record):
    """
    Including the rev in the key means that the record will be unlocked for processing
    every time we execute a `save()` call.
    """
    return 'repeat_record_in_progress-{}_{}'.format(record._id, record._rev)


repeaters_overdue = datadog_gauge_task(
    'commcare.repeaters.overdue',
    get_overdue_repeat_record_count,
    run_every=crontab()  # every minute
)
