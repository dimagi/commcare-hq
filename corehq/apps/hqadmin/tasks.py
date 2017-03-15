from datetime import date, timedelta

from celery.schedules import crontab
from celery.task.base import periodic_task

from corehq.apps.hqadmin.models import HistoricalPillowCheckpoint
from .utils import check_pillows_for_rewind


@periodic_task(run_every=crontab(hour=0, minute=0), queue='background_queue')
def pillow_seq_store_task():
    check_pillows_for_rewind()


@periodic_task(run_every=crontab(hour=0, minute=0), queue='background_queue')
def create_es_snapshot_checkpoints():
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    HistoricalPillowCheckpoint.create_pillow_checkpoint_snapshots()
    HistoricalPillowCheckpoint.objects.filter(date_updated__lt=thirty_days_ago).delete()
