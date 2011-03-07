from celery.schedules import crontab
from celery.decorators import periodic_task
from celery.task import task
from datetime import datetime
from couchforms.models import XFormInstance
from couchdbkit.resource import ResourceNotFound
from dimagi.utils.post import post_data, simple_post
from dimagi.utils.parsing import json_format_datetime, ISO_MIN

@periodic_task(run_every=crontab(hour="*", minute="*/15", day_of_week="*"))
def check_repeaters():
    # this should get called every 15 minutes by celery
    now = datetime.utcnow()
    pending_forms = XFormInstance.get_db().view("receiverwrapper/forms_with_pending_repeats", 
                                                startkey=json_format_datetime(ISO_MIN), 
                                                endkey=json_format_datetime(now)).all()
    for row in pending_forms:
        send_repeats(row["id"])
            

@task(ignore_result=True)
def send_repeats(form_id, max_tries=3):
    """
    Send a repeat from the form to the repeater
    """
    from corehq.apps.receiverwrapper.models import RepeatRecord
    try:
        form = XFormInstance.get(form_id)
    except ResourceNotFound:
        # this is odd, but we won't worry about it. Maybe the form was deleted
        return
    if "repeats" in form:
        updated = False
        for i, repeat in enumerate(form.repeats):
            repeat = RepeatRecord.wrap(repeat)
            if repeat.try_now():
                # we don't use celery's version of retry because 
                # we want to override the success/fail each try
                tries = 0
                while tries < max_tries:
                    tries += 1
                    try:
                        resp = simple_post(form.get_xml(), repeat.url)
                        if 200 <= resp.status < 300:
                            repeat.update_success()
                            break
                    except Exception:
                        pass # some other connection issue probably
                if not repeat.succeeded:
                    # mark it failed for later and give up
                    repeat.update_failure()
                updated = True
                form.repeats[i] = repeat.to_json()
        if updated:
            form.save()
            