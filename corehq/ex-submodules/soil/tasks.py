from celery.task import periodic_task
from celery.schedules import crontab
from soil.heartbeat import write_file_heartbeat, write_cache_heartbeat
from django.conf import settings


@periodic_task(run_every=crontab(hour="*", minute="*", day_of_week="*"),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def heartbeat():
    """
    A heartbeat, used to confirm that celery is alive and kicking.

    This heartbeat will stop if either celery or celeryd go down.
    """
    write_file_heartbeat()
    write_cache_heartbeat()
