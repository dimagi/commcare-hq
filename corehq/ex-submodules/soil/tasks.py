from celery.task import task, periodic_task
from celery.schedules import crontab
from soil.heartbeat import write_file_heartbeat, write_cache_heartbeat
from soil.util import expose_cached_download
from django.conf import settings


@task(serializer='pickle')
def prepare_download(download_id, payload_func, content_disposition,
                     content_type, expiry=10*60*60):
    """
    payload_func should be an instance of SerializableFunction, and can return
    either a string or a FileWrapper object
    """
    try:
        payload = payload_func(process=prepare_download)
    except TypeError:
        payload = payload_func()
    expose_cached_download(payload, expiry, None, mimetype=content_type,
                           content_disposition=content_disposition,
                           download_id=download_id)


@periodic_task(run_every=crontab(hour="*", minute="*", day_of_week="*"),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def heartbeat():
    """
    A heartbeat, used to confirm that celery is alive and kicking.

    This heartbeat will stop if either celery or celeryd go down.
    """
    write_file_heartbeat()
    write_cache_heartbeat()
