from datetime import date, timedelta

from celery.schedules import crontab
from celery.task.base import periodic_task

from corehq.apps.hqadmin.models import ESRestorePillowCheckpoints
from .utils import pillow_seq_store


@periodic_task(run_every=crontab(hour=0, minute=0), queue='background_queue')
def pillow_seq_store_task():
    pillow_seq_store()


@periodic_task(run_every=crontab(hour=0, minute=0), queue='background_queue')
def create_es_snapshot_checkpoints():
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    ESRestorePillowCheckpoints.create_pillow_checkpoint_snapshots()
    ESRestorePillowCheckpoints.objects.filter(date_updated__lt=thirty_days_ago).delete()
