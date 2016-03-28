from celery.schedules import crontab
from celery.task.base import periodic_task

from .utils import pillow_seq_store


@periodic_task(run_every=crontab(hour=0, minute=0), queue='background_queue')
def pillow_seq_store_task():
    pillow_seq_store()
