from functools import wraps
from celery.log import get_task_logger
from celery.task import periodic_task
from datetime import datetime, timedelta
from django.core.cache import cache
from corehq.apps.receiverwrapper.models import RepeatRecord, FormRepeater
from couchdbkit.exceptions import ResourceConflict
from couchforms.models import XFormInstance
from dimagi.utils.parsing import json_format_datetime, ISO_MIN

logging = get_task_logger()

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

@periodic_task(run_every=timedelta(minutes=1))
def check_repeaters():
    now = datetime.utcnow()
    
    repeat_records = RepeatRecord.all(due_before=now)
    for repeat_record in repeat_records:
        if repeat_record.acquire_lock(now):
            repeat_record.fire()
            repeat_record.save()
            repeat_record.release_lock()