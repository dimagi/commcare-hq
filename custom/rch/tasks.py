from celery.task import periodic_task
from celery.schedules import crontab

from custom.rch.models import (
    RCHMotherRecord,
    RCHChildRecord,
)


# fetch mother records every day at 6pm IST
@periodic_task(run_every=crontab(minute="0", hour="18"), queue='background_queue')
def fetch_rch_mother_beneficiaries():
    RCHMotherRecord.update_beneficiaries()


# fetch child records every day at 6:15pm IST
@periodic_task(run_every=crontab(minute="15", hour="18"), queue='background_queue')
def fetch_rch_child_beneficiaries():
    RCHChildRecord.update_beneficiaries()
