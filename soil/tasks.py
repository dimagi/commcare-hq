from celery.decorators import task
import time
from django.core.cache import cache

@task
def demo_sleep(download_id, howlong=5, expiry=1*60*60):
    """
    Demo the downloader, with sleep
    """
    time.sleep(howlong)
    cache.set(download_id, "It works!", expiry)
