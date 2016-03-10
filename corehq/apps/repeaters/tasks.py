from datetime import datetime

from django.conf import settings
from dimagi.utils.couch import LockManager
from celery.task import periodic_task, task
from celery.utils.log import get_task_logger
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.apps.repeaters.dbaccessors import iterate_repeat_records
from corehq.apps.repeaters.models import RepeatRecord
from corehq.apps.repeaters.const import (
    CHECK_REPEATERS_INTERVAL,
    RECORDS_IN_PROGRESS_REDIS_KEY,
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

    for record in iterate_repeat_records(start):
        now = datetime.utcnow()

        if now > cutoff:
            break

        if redis_client.sismember(RECORDS_IN_PROGRESS_REDIS_KEY, record._id):
            continue

        process_repeat_record.delay(record)


@task(queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeat_record(repeat_record):
    redis_client = get_redis_client().client.get_client()

    redis_client.sadd(RECORDS_IN_PROGRESS_REDIS_KEY, repeat_record._id)
    try:
        lock = RepeatRecord.get_obj_lock(repeat_record)
        lock.acquire()

        with LockManager(repeat_record, lock) as record:
            if record.repeater.doc_type.endswith(DELETED_SUFFIX):
                if not record.doc_type.endswith(DELETED_SUFFIX):
                    record.doc_type += DELETED_SUFFIX
            else:
                record.fire()
            record.save()
    except Exception:
        logging.exception('Failed to process repeat record: {}'.format(repeat_record._id))
    finally:
        redis_client.srem(RECORDS_IN_PROGRESS_REDIS_KEY, record._id)
