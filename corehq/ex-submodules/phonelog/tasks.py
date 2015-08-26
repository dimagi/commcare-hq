from datetime import datetime, timedelta
from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings
from phonelog.models import DeviceReportEntry


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def purge_old_device_report_entries():
    max_age = datetime.utcnow() - timedelta(days=60)
    DeviceReportEntry.objects.filter(server_date__lt=max_age).delete()
