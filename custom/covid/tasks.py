from datetime import datetime

from celery.exceptions import MaxRetriesExceededError
from celery.schedules import crontab
from celery.task import periodic_task
from dateutil.relativedelta import relativedelta

from casexml.apps.phone.models import SyncLogSQL
from corehq.apps.domain.auth import FORMPLAYER
from corehq.apps.formplayer_api.exceptions import FormplayerResponseException
from corehq.apps.formplayer_api.sync_db import sync_db
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import raw_username
from corehq.toggles import PRIME_FORMPLAYER_DBS
from corehq.util.celery_utils import no_result_task
from corehq.util.metrics import metrics_counter
from dimagi.utils.logging import notify_exception
from django.conf import settings

SYNC_WINDOW_HOURS = 48
SYNC_CUTOFF_HOURS = 8

MIN_CASE_COUNT = 20000


@periodic_task(run_every=crontab(minute=0, hour=8), queue=settings.CELERY_PERIODIC_QUEUE)
def prime_formplayer_dbs():
    domains = PRIME_FORMPLAYER_DBS.get_enabled_domains()
    date_window = datetime.utcnow() - relativedelta(hours=SYNC_WINDOW_HOURS)
    date_cutoff = datetime.utcnow() - relativedelta(hours=SYNC_CUTOFF_HOURS)
    for domain in domains:
        users = get_users_for_priming(domain, date_window, date_cutoff, MIN_CASE_COUNT)
        for row in users:
            prime_formplayer_db_for_user.delay(domain, row[0], row[1])


@no_result_task(queue='async_restore_queue', max_retries=3, bind=True, rate_limit=50)
def prime_formplayer_db_for_user(self, domain, request_user_id, sync_user_id):
    request_user, as_username = get_prime_restore_user_params(request_user_id, sync_user_id)

    metric_tags = {"domain": domain}
    try:
        sync_db(domain, request_user, as_username)
    except FormplayerResponseException:
        notify_exception(None, "Error while priming formplayer user DB", details={
            'domain': domain,
            'username': request_user,
            'as_user': as_username
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


def get_prime_restore_user_params(request_user_id, sync_user_id):
    """Return username param and as_user param for performing formpalyer sync"""
    request_user = CouchUser.get_by_user_id(request_user_id).username
    as_username = None
    if sync_user_id != request_user_id:
        as_user = CouchUser.get_by_user_id(sync_user_id)
        as_username = raw_username(as_user.username) if as_user else None
    return request_user, as_username


def get_users_for_priming(domain, sync_window, sync_cutoff, min_case_load):
    """Return a list of (request_user_id, user_id) tuples that match the criteria:

    - user has synced since ``since_window``
    - user has not synced since ``sync_cutoff``
    - user has a case load > ``min_case_load``
    """
    assert sync_window > sync_cutoff

    users_synced_in_window = set(
        SyncLogSQL.objects.values("request_user_id", "user_id")
        .filter(
            domain=domain,
            date__gt=sync_window,
            is_formplayer=True,
            case_count__gt=min_case_load
        ).exclude(auth_type=FORMPLAYER)  # ignore syncs that were done by SMS or by this task
        .distinct()
    )

    users_synced_since_cutoff = set(
        SyncLogSQL.objects.values_list("request_user_id", "user_id")
        .filter(domain=domain, date__gt=sync_cutoff, is_formplayer=True)
        .exclude(auth_type=FORMPLAYER)
        .distinct()
    )

    return list(users_synced_in_window - users_synced_since_cutoff)
