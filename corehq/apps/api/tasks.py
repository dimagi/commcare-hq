from __future__ import absolute_import
from __future__ import unicode_literals
import time
from celery.schedules import crontab
from celery.task.base import periodic_task
from tastypie.models import ApiAccess


@periodic_task(run_every=crontab(minute=0, hour=0), queue='background_queue')
def clean_api_access():
    accessed = int(time.time()) - 90 * 24 * 3600  # only keep last 30 days
    ApiAccess.objects.filter(accessed__lt=accessed).delete()
