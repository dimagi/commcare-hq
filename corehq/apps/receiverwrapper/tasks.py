from functools import wraps

from datetime import datetime, timedelta
import json
from celery.task import periodic_task
from celery.utils.log import get_task_logger
from django.core.cache import cache
from django.conf import settings

from corehq.apps.receiverwrapper.models import RepeatRecord

logging = get_task_logger(__name__)

def run_only_once(fn):
    """
    If this function is running (in any thread) then don't run

    Updated with some help from:
    http://ask.github.com/celery/cookbook/tasks.html#ensuring-a-task-is-only-executed-one-at-a-time
    """
    LOCK_EXPIRE = 10*60
    fn_name = fn.__module__ + '.' + fn.__name__
    lock_id = fn_name + '_is_running'
    acquire_lock = lambda: cache.add(lock_id, "true", LOCK_EXPIRE)
    release_lock = lambda: cache.delete(lock_id)

    @wraps(fn)
    def _fn(*args, **kwargs):
        if acquire_lock():
            try:
                return fn(*args, **kwargs)
            finally:
                release_lock()
        else:
            logging.debug("%s is already running; aborting" % fn_name)
    return _fn

CHECK_REPEATERS_INTERVAL = timedelta(minutes=1)
@periodic_task(run_every=CHECK_REPEATERS_INTERVAL, queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def check_repeaters():
    start = datetime.utcnow()
    LIMIT = 100
    DELETED = '-Deleted'
    progress_report = {'success': [], 'fail': [], 'locked': [], 'deleted': []}

    def loop():
        number_locked = 0
        # take LIMIT records off the top
        # the assumption is that they all get 'popped' in the for loop
        # the only exception I can see is if there's a problem with the
        # locking, a large number of locked tasks could pile up at the top,
        # so make a provision for that worst case
        repeat_records = RepeatRecord.all(
            due_before=start,
            limit=LIMIT + number_locked
        )
        if repeat_records.count() <= number_locked:
            # don't keep spinning if there's nothing left to fetch
            return False

        for repeat_record in repeat_records:
            now = datetime.utcnow()

            # abort if taking too long, so the next task can take over
            if now - start > CHECK_REPEATERS_INTERVAL:
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
                number_locked += 1
        return True

    while loop():
        pass

    now = datetime.utcnow()
    progress_report['timedelta'] = unicode(now - start)
    progress_report['time'] = unicode(now)
    logging.info(json.dumps(progress_report))
