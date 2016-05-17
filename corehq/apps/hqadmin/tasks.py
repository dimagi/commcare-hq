from celery.schedules import crontab
from celery.task import task
from celery.task.base import periodic_task

from .utils import pillow_seq_store


@periodic_task(run_every=crontab(hour=0, minute=0), queue='background_queue')
def pillow_seq_store_task():
    pillow_seq_store()


@task(queue='background_queue')
def dummy_task():
    """Dummy task to make sure celery is up and working"""
    return "expected return value"
