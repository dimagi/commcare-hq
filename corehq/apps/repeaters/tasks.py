from datetime import datetime, timedelta
import json
from celery.task import periodic_task
from celery.utils.log import get_task_logger
from django.conf import settings

from corehq.apps.repeaters.models import RepeatRecord

logging = get_task_logger(__name__)

CHECK_REPEATERS_INTERVAL = timedelta(minutes=5)
@periodic_task(run_every=CHECK_REPEATERS_INTERVAL, queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def check_repeaters():
    start = datetime.utcnow()
    LIMIT = 100
    progress_report = new_progress_report()

    def loop():
        # take LIMIT records off the top
        # the assumption is that they all get 'popped' in the for loop
        # the only exception I can see is if there's a problem with the
        # locking, a large number of locked tasks could pile up at the top,
        # so make a provision for that worst case
        number_locked = progress_report['number_locked']
        repeat_records = RepeatRecord.all(
            due_before=start,
            limit=LIMIT + number_locked
        )
        return process_repeater_list(
            repeat_records,
            start=start,
            cutoff=start + CHECK_REPEATERS_INTERVAL,
            progress_report=progress_report
        )

    while loop():
        pass

    now = datetime.utcnow()
    progress_report['timedelta'] = unicode(now - start)
    progress_report['time'] = unicode(now)
    logging.info(json.dumps(progress_report))


def new_progress_report():
    return {'success': [], 'fail': [], 'locked': [], 'deleted': [], 'number_locked': 0}


def process_repeater_list(repeat_records, start=None, cutoff=datetime.max, progress_report=None):
    """
    Attempts to process a list of repeat records, with a bunch of optional arguments that are
    used by the periodic task.
    """
    start = start or datetime.utcnow()
    progress_report = progress_report or new_progress_report()
    DELETED = '-Deleted'

    if repeat_records.count() <= progress_report['number_locked']:
        # don't keep spinning if there's nothing left to fetch
        return False

    for repeat_record in repeat_records:
        now = datetime.utcnow()

        # abort if taking too long, so the next task can take over
        if now > cutoff:
            return False

        if repeat_record.acquire_lock(start):
            if repeat_record.repeater.doc_type.endswith(DELETED):
                if not repeat_record.doc_type.endswith(DELETED):
                    repeat_record.doc_type += DELETED
                progress_report['deleted'].append(repeat_record.get_id)
            else:
                repeat_record.fire()
                if repeat_record.succeeded:
                    progress_report['success'].append(repeat_record.get_id)
                else:
                    progress_report['fail'].append(repeat_record.get_id)
            repeat_record.save()
            repeat_record.release_lock()
        else:
            progress_report['locked'].append(repeat_record.get_id)
            progress_report['number_locked'] += 1

    return progress_report
