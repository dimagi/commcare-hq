from datetime import datetime

from django.conf import settings
from celery.task import periodic_task
from celery.utils.log import get_task_logger
from corehq.util.celery_utils import hqtask
from redis.exceptions import LockError
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.apps.repeaters.dbaccessors import iterate_repeat_records
from corehq.apps.repeaters.const import (
    CHECK_REPEATERS_INTERVAL,
    CHECK_REPEATERS_KEY,
)

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


@hqtask(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeat_record(repeat_record):
    try:
        if repeat_record.repeater.doc_type.endswith(DELETED_SUFFIX):
            if not repeat_record.doc_type.endswith(DELETED_SUFFIX):
                repeat_record.doc_type += DELETED_SUFFIX
        else:
            repeat_record.fire()
        repeat_record.save()
    except Exception:
        logging.exception('Failed to process repeat record: {}'.format(repeat_record._id))


def _get_repeat_record_lock_key(record):
    """
    Including the rev in the key means that the record will be unlocked for processing
    every time we execute a `save()` call.
    """
    return 'repeat_record_in_progress-{}_{}'.format(record._id, record._rev)
