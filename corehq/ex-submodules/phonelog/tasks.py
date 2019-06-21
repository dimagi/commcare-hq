from __future__ import absolute_import

from __future__ import unicode_literals
from datetime import datetime, timedelta

from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings
from django.db import connection
from requests import Session
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException

from corehq.util.celery_utils import no_result_task
from phonelog.models import ForceCloseEntry, UserEntry, UserErrorEntry


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def purge_old_device_report_entries():
    max_age = datetime.utcnow() - timedelta(days=settings.DAYS_TO_KEEP_DEVICE_LOGS)
    with connection.cursor() as cursor:
        partitoned_db_format = 'phonelog_daily_partitioned_devicereportentry_y%Yd%j'
        table_to_drop = (max_age - timedelta(days=1)).strftime(partitoned_db_format)
        cursor.execute("DROP TABLE IF EXISTS {}".format(table_to_drop))
    UserErrorEntry.objects.filter(server_date__lt=max_age).delete()
    ForceCloseEntry.objects.filter(server_date__lt=max_age).delete()
    UserEntry.objects.filter(server_date__lt=max_age).delete()


@no_result_task(serializer='pickle', queue='sumologic_logs_queue', default_retry_delay=10 * 60, max_retries=3, bind=True)
def send_device_log_to_sumologic(self, url, data, headers):
    with Session() as s:
        s.mount(url, HTTPAdapter(max_retries=5))
        try:
            s.post(url, data=data, headers=headers, timeout=5)
        except RequestException as e:
            self.retry(exc=e)
