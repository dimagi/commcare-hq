from __future__ import absolute_import
from __future__ import unicode_literals
from celery.task import task, periodic_task
import time
from django.core.cache import cache
from soil import CachedDownload
import uuid
from celery.schedules import crontab
from soil.heartbeat import write_file_heartbeat, write_cache_heartbeat
from soil.util import expose_cached_download
from django.conf import settings


@task(serializer='pickle')
def demo_sleep(download_id, howlong=5, expiry=1*60*60):
    """
    Demo the downloader, with sleep
    """
    time.sleep(howlong)
    temp_id = uuid.uuid4().hex
    cache.set(temp_id, "It works!", expiry)
    cache.set(download_id, CachedDownload(temp_id), expiry)


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
