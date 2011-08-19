from celery.decorators import task
import time
from django.core.cache import cache
from soil import CachedDownload
import uuid

@task
def demo_sleep(download_id, howlong=5, expiry=1*60*60):
    """
    Demo the downloader, with sleep
    """
    time.sleep(howlong)
    temp_id = download_id = uuid.uuid4().hex
    cache.set(temp_id, "It works!", expiry)
    cache.set(download_id, CachedDownload(temp_id), expiry)
