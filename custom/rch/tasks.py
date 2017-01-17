from celery.task import periodic_task
from celery.schedules import crontab

from custom.rch.models import RCHMother, RCHChild


@periodic_task(run_every=crontab(minute="0", hour="6"), queue='background_queue')
def fetch_rch_mother_beneficiaries():
    RCHMother.update_beneficiaries()


@periodic_task(run_every=crontab(minute="15", hour="6"), queue='background_queue')
def fetch_rch_child_beneficiaries():
    RCHChild.update_beneficiaries()
