from datetime import datetime

from celery.schedules import crontab
from dateutil.relativedelta import relativedelta

from corehq.apps.celery import periodic_task
from corehq.toggles import PRIME_FORMPLAYER_DBS_BHA, SKIP_FIXTURES_ON_RESTORE

from corehq.apps.formplayer_api.tasks import (
    prime_formplayer_db_for_user,
    get_users_for_priming,
)


# Include users that have synced in the last 2 weeks
SYNC_WINDOW_HOURS = 24 * 14

# 10th percentile of first form submission occurs by 7AM GMT-7. The task should be completed by then to be useful.
# Don't allow tasks to run beyond then (2PM UTC).
TASK_WINDOW_CUTOFF_HOUR = 14

PRIME_FORMPLAYER_HOUR = 12
REENABLE_FEATURE_FLAG_HOUR = PRIME_FORMPLAYER_HOUR + 1


# Start priming at 12PM UTC (5AM GMT-7) so that the task is completed by 2PM UTC (7AM GMT-7).
@periodic_task(run_every=crontab(minute=0, hour=PRIME_FORMPLAYER_HOUR), queue='ush_background_tasks')
def bha_prime_formplayer_dbs():
    domains = PRIME_FORMPLAYER_DBS_BHA.get_enabled_domains()
    for domain in domains:
        SKIP_FIXTURES_ON_RESTORE.set(domain, False, 'domain')
    date_window = datetime.utcnow() - relativedelta(hours=SYNC_WINDOW_HOURS)
    for domain in domains:
        users = get_users_for_priming(domain, date_window)
        for row in users:
            prime_formplayer_db_for_user.delay(domain, row[0], row[1], task_cutoff_hour=TASK_WINDOW_CUTOFF_HOUR)


# This is temporary while investigating restore slowness caused by fixtures.
@periodic_task(run_every=crontab(minute=0, hour=REENABLE_FEATURE_FLAG_HOUR), queue='ush_background_tasks')
def reenable_skip_fixtures_feature_flag():
    domains = PRIME_FORMPLAYER_DBS_BHA.get_enabled_domains()
    for domain in domains:
        SKIP_FIXTURES_ON_RESTORE.set(domain, True, 'domain')
