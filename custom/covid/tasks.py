from datetime import datetime

from celery.exceptions import MaxRetriesExceededError
from celery.schedules import crontab
from dateutil.relativedelta import relativedelta

from dimagi.utils.logging import notify_exception

from corehq.apps.celery import periodic_task
from corehq.apps.formplayer_api.clear_user_data import clear_user_data
from corehq.apps.formplayer_api.exceptions import FormplayerAPIException

from corehq.toggles import PRIME_FORMPLAYER_DBS
from corehq.util.celery_utils import no_result_task

from custom.formplayer.restore_priming import (
    prime_formplayer_db_for_user,
    get_users_for_priming,
    get_prime_restore_user_params,
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


@no_result_task(queue='ush_background_tasks', max_retries=3, bind=True)
def clear_formplayer_db_for_user(self, domain, request_user_id, sync_user_id):
    request_user, as_username = get_prime_restore_user_params(request_user_id, sync_user_id)

    try:
        clear_user_data(domain, request_user, as_username)
    except FormplayerAPIException:
        notify_exception(None, "Error while clearing formplayer user DB", details={
            'domain': domain,
            'username': request_user,
            'as_user': as_username,
        })
    except Exception as e:
        # most likely an error contacting formplayer, try again
        try:
            raise self.retry(exc=e)
        except MaxRetriesExceededError:
            raise
