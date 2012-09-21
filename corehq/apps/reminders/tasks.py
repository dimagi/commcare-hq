from datetime import timedelta
from celery.task import periodic_task
from corehq.apps.reminders.models import CaseReminderHandler

@periodic_task(run_every=timedelta(minutes=1))
def fire_reminders():
    CaseReminderHandler.fire_reminders()