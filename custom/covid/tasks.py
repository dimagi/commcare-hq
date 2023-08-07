from datetime import datetime

from django.conf import settings

from celery.exceptions import MaxRetriesExceededError
from celery.schedules import crontab
from dateutil.relativedelta import relativedelta

from casexml.apps.phone.models import SyncLogSQL
from dimagi.utils.logging import notify_exception

from corehq.apps.celery import periodic_task
from corehq.apps.domain.auth import FORMPLAYER
from corehq.apps.formplayer_api.clear_user_data import clear_user_data
from corehq.apps.formplayer_api.exceptions import FormplayerAPIException
from corehq.apps.formplayer_api.sync_db import sync_db
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import raw_username
from corehq.toggles import PRIME_FORMPLAYER_DBS
from corehq.util.celery_utils import no_result_task
from corehq.util.metrics import metrics_counter

RATE_LIMIT = getattr(settings, 'USH_PRIME_RESTORE_RATE_LIMIT', 100)

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


@no_result_task(queue='ush_background_tasks', max_retries=3, bind=True, rate_limit=RATE_LIMIT)
def prime_formplayer_db_for_user(self, domain, request_user_id, sync_user_id,
                                 clear_data=False, task_cutoff_hour=None):
    if task_cutoff_hour and datetime.utcnow().hour >= task_cutoff_hour:
        return

    request_user, as_username = get_prime_restore_user_params(request_user_id, sync_user_id)

    metric_tags = {"domain": domain}
    try:
        if clear_data:
            clear_user_data(domain, request_user, as_username)
        sync_db(domain, request_user, as_username)
    except FormplayerAPIException:
        notify_exception(None, "Error while priming formplayer user DB", details={
            'domain': domain,
            'username': request_user,
            'as_user': as_username,
            'clear_user_data': clear_data
        })
        metrics_counter("commcare.prime_formplayer_db.error", tags=metric_tags)
    except Exception as e:
        # most likely an error contacting formplayer, try again
        try:
            raise self.retry(exc=e)
        except MaxRetriesExceededError:
            metrics_counter("commcare.prime_formplayer_db.error", tags=metric_tags)
            raise
    else:
        metrics_counter("commcare.prime_formplayer_db.success", tags=metric_tags)


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


def get_prime_restore_user_params(request_user_id, sync_user_id):
    """Return username param and as_user param for performing formpalyer sync"""
    request_user = CouchUser.get_by_user_id(request_user_id).username
    as_username = None
    if sync_user_id and sync_user_id != request_user_id:
        as_user = CouchUser.get_by_user_id(sync_user_id)
        as_username = raw_username(as_user.username) if as_user else None
    return request_user, as_username


def get_users_for_priming(domain, sync_window, sync_cutoff=None, min_case_load=None):
    """Return a list of (request_user_id, user_id) tuples that match the criteria:

    - user has synced since ``since_window``
    - user has not synced since ``sync_cutoff``
    - user has a case load > ``min_case_load``
    """
    if sync_cutoff:
        assert sync_window < sync_cutoff, "Sync cutoff time must be within the sync window"

    base_query = (
        SyncLogSQL.objects.values_list("request_user_id", "user_id")
        .filter(
            domain=domain,
            is_formplayer=True,
        ).exclude(auth_type=FORMPLAYER)  # ignore syncs that were done by SMS or by this task
    )

    query = base_query.filter(date__gt=sync_window)
    if min_case_load:
        query = query.filter(case_count__gt=min_case_load)
    users_synced_in_window = set(query.distinct())

    if sync_cutoff:
        users_synced_since_cutoff = set(base_query.filter(date__gt=sync_cutoff).distinct())
        return list(users_synced_in_window - users_synced_since_cutoff)

    return list(users_synced_in_window)
