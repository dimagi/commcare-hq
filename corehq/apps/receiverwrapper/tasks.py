from celery.schedules import crontab
from celery.decorators import periodic_task
from celery.task import task
from datetime import datetime
from corehq.apps.receiverwrapper.models import RepeatRecord, FormRepeater
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
        repeat_record.save()

@periodic_task(run_every=crontab(hour="*", minute="*/15", day_of_week="*"))
def check_inline_form_repeaters(post_fn=None):
    """old-style FormRepeater grandfathered in"""
    now = datetime.utcnow()
    forms = XFormInstance.view('receiverwrapper/forms_with_pending_repeats',
        startkey="",
        endkey=json_format_datetime(now),
        include_docs=True,
    )

    for form in forms:
        if hasattr(form, 'repeats'):
            for repeat_record in form.repeats:
                record = dict(repeat_record)
                url = record.pop('url')
                record = RepeatRecord.wrap(record)
                record.payload_id = form.get_id

                record._repeater = FormRepeater(url=url)
                record.fire(post_fn=post_fn)
                record = record.to_json()
                record['url'] = url
                repeat_record.update(record)
            form.save()