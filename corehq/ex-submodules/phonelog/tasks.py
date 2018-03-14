from __future__ import absolute_import

from __future__ import unicode_literals
from datetime import datetime, timedelta

from celery.schedules import crontab
from celery.task import periodic_task, task
from django.conf import settings
from django.db import connection

from phonelog.models import ForceCloseEntry, UserEntry, UserErrorEntry
from phonelog.utils import SumoLogicLog


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def purge_old_device_report_entries():
    max_age = datetime.utcnow() - timedelta(days=settings.DAYS_TO_KEEP_DEVICE_LOGS)
    with connection.cursor() as cursor:
        partitoned_db_format = 'phonelog_daily_partitioned_devicereportentry_y%Yd%j'
        table_to_drop = (max_age - timedelta(days=1)).strftime(partitoned_db_format)
        cursor.execute("DROP TABLE {}".format(table_to_drop))
    UserErrorEntry.objects.filter(server_date__lt=max_age).delete()
    ForceCloseEntry.objects.filter(server_date__lt=max_age).delete()
    UserEntry.objects.filter(server_date__lt=max_age).delete()


@task(queue='sumologic_logs_queue')
def send_device_logs_to_sumologic(domain, xform, url):
    SumoLogicLog(domain, xform).send_data(url)
