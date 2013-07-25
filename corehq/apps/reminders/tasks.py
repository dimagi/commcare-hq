from datetime import timedelta
from celery.task import periodic_task
from corehq.apps.reminders.models import CaseReminderHandler
from django.conf import settings

@periodic_task(run_every=timedelta(minutes=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def fire_reminders():
    CaseReminderHandler.fire_reminders()