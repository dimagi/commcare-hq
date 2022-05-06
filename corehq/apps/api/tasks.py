import time

from celery.schedules import crontab
from tastypie.models import ApiAccess
from corehq.apps.celery import periodic_task


@periodic_task(run_every=crontab(minute=0, hour=0), queue='background_queue')
def clean_api_access():
    accessed = int(time.time()) - 90 * 24 * 3600  # only keep last 90 days
    ApiAccess.objects.filter(accessed__lt=accessed).delete()
