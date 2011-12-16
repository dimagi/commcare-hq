from celery.schedules import crontab
from celery.decorators import periodic_task
from celery.task import task
from datetime import datetime
from corehq.apps.receiverwrapper.models import RepeatRecord
from couchforms.models import XFormInstance
from couchdbkit.resource import ResourceNotFound
from dimagi.utils.parsing import json_format_datetime, ISO_MIN

@periodic_task(run_every=crontab(hour="*", minute="*/15", day_of_week="*"))
def check_repeaters():
    # this should get called every 15 minutes by celery
    now = datetime.utcnow()

    repeat_records = RepeatRecord.all(due_before=now)

    for repeat_record in repeat_records:
        repeat_record.fire()
