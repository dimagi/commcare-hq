from celery.task import task, periodic_task
import time
from django.core.cache import cache
from soil import CachedDownload
import uuid
from celery.schedules import crontab
from soil.heartbeat import write_file_heartbeat, write_cache_heartbeat

@task
def demo_sleep(download_id, howlong=5, expiry=1*60*60):
    """
    Demo the downloader, with sleep
    """
    time.sleep(howlong)
    temp_id = uuid.uuid4().hex
    cache.set(temp_id, "It works!", expiry)
    cache.set(download_id, CachedDownload(temp_id), expiry)

@periodic_task(run_every=crontab(hour="*", minute="*", day_of_week="*"))
def heartbeat():
    """
    A heartbeat, used to confirm that celery is alive and kicking.
    
    This heartbeat will stop if either celery or celeryd go down.
    """
    write_file_heartbeat()
    write_cache_heartbeat()
        
