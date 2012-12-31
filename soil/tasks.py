from celery.task import task, periodic_task
import time
from django.core.cache import cache
from django.core.servers.basehttp import FileWrapper
from soil import CachedDownload, FileDownload
import uuid
from celery.schedules import crontab
from soil.heartbeat import write_file_heartbeat, write_cache_heartbeat
from soil.util import expose_download

@task
def demo_sleep(download_id, howlong=5, expiry=1*60*60):
    """
    Demo the downloader, with sleep
    """
    time.sleep(howlong)
    temp_id = uuid.uuid4().hex
    cache.set(temp_id, "It works!", expiry)
    cache.set(download_id, CachedDownload(temp_id), expiry)

@task
def prepare_download(download_id, payload_func, content_disposition, mimetype, expiry=10*60*60):
    """
    payload_func should be an instance of SerializableFunction, and can return
    either a string or a FileWrapper object
    """
    payload = payload_func()
    # I don't know if this is too sneaky/magical to be OK
    if isinstance(payload, FileWrapper):
        backend = FileDownload
    else:
        backend = None
    expose_download(payload, expiry, mimetype=mimetype,
                    content_disposition=content_disposition,
                    download_id=download_id, backend=backend)
    

@periodic_task(run_every=crontab(hour="*", minute="*", day_of_week="*"))
def heartbeat():
    """
    A heartbeat, used to confirm that celery is alive and kicking.
    
    This heartbeat will stop if either celery or celeryd go down.
    """
    write_file_heartbeat()
    write_cache_heartbeat()
        
    