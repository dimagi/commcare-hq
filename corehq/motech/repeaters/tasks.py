from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime, timedelta

from celery.schedules import crontab
from celery.task import periodic_task, task
from celery.utils.log import get_task_logger
from django.conf import settings

from corehq.motech.repeaters.const import (
    CHECK_REPEATERS_INTERVAL,
    CHECK_REPEATERS_KEY,
    RECORD_PENDING_STATE,
    RECORD_FAILURE_STATE,
)
from corehq.motech.repeaters.dbaccessors import (
    iterate_repeat_records,
    get_overdue_repeat_record_count,
)
from corehq.util.datadog.gauges import datadog_gauge_task
from corehq.util.soft_assert import soft_assert
from dimagi.utils.couch import get_redis_lock
from dimagi.utils.couch.undo import DELETED_SUFFIX


_soft_assert = soft_assert(to='@'.join(('nhooper', 'dimagi.com')))
logging = get_task_logger(__name__)


@periodic_task(
    run_every=CHECK_REPEATERS_INTERVAL,
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def check_repeaters():
    start = datetime.utcnow()
    six_hours_later = start + timedelta(hours=6)

    # Long timeout to allow all waiting repeat records to be iterated
    check_repeater_lock = get_redis_lock(
        CHECK_REPEATERS_KEY,
        name=CHECK_REPEATERS_KEY,
    )
    if not check_repeater_lock.acquire(blocking=False):
        return

    try:
        for record in iterate_repeat_records(start):
            if datetime.utcnow() > six_hours_later:
                _soft_assert(False, "I've been iterating repeat records for six hours. I quit!")
                break

            if record.can_enqueue():
                process_repeat_record.delay(record)
    finally:
        check_repeater_lock.release()


@task(serializer='pickle', queue=settings.CELERY_REPEAT_RECORD_QUEUE)
def process_repeat_record(repeat_record):
    if repeat_record.state == RECORD_FAILURE_STATE and repeat_record.overall_tries >= repeat_record.max_possible_tries:
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
            # postpone repeat record by 1 hour so that these don't get picked in each cycle and
            # thus clogging the queue with repeat records with paused repeater
            repeat_record.postpone_by(timedelta(hours=1))
            return
        if repeater.doc_type.endswith(DELETED_SUFFIX):
            if not repeat_record.doc_type.endswith(DELETED_SUFFIX):
                repeat_record.doc_type += DELETED_SUFFIX
                repeat_record.save()
        elif repeat_record.state == RECORD_PENDING_STATE or repeat_record.state == RECORD_FAILURE_STATE:
                repeat_record.fire()
    except Exception:
        logging.exception('Failed to process repeat record: {}'.format(repeat_record._id))


repeaters_overdue = datadog_gauge_task(
    'commcare.repeaters.overdue',
    get_overdue_repeat_record_count,
    run_every=crontab()  # every minute
)
