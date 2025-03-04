from datetime import datetime

from celery.schedules import crontab
from dateutil.relativedelta import relativedelta

from corehq.apps.celery import periodic_task

from corehq.toggles import PRIME_FORMPLAYER_DBS

from custom.formplayer.restore_priming import (
    prime_formplayer_db_for_user,
    get_users_for_priming,
)


# Include users that have synced in the last 72 hours
SYNC_WINDOW_HOURS = 72

# Exclude users that have synced in the last 8 hours
SYNC_CUTOFF_HOURS = 8

# Exclude users whose case load is less than this
MIN_CASE_COUNT = 1000

# Don't allow tasks to run beyond 11am UTC
TASK_WINDOW_CUTOFF_HOUR = 11


@periodic_task(run_every=crontab(minute=0, hour=8), queue='ush_background_tasks')
def prime_formplayer_dbs():
    domains = PRIME_FORMPLAYER_DBS.get_enabled_domains()
    date_window = datetime.utcnow() - relativedelta(hours=SYNC_WINDOW_HOURS)
    date_cutoff = datetime.utcnow() - relativedelta(hours=SYNC_CUTOFF_HOURS)
    for domain in domains:
        users = get_users_for_priming(domain, date_window, date_cutoff, MIN_CASE_COUNT)
        for row in users:
            prime_formplayer_db_for_user.delay(domain, row[0], row[1], task_cutoff_hour=TASK_WINDOW_CUTOFF_HOUR)
