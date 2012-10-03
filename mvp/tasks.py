from celery.schedules import crontab, schedule
from celery.task import periodic_task, task
from mvp.management.commands import mvp_update_existing

#@periodic_task(run_every=crontab(minute=0, hour=[0, 12]))
def update_mvp_indicators():
    update_existing = mvp_update_existing.Command()
    update_existing.handle()
