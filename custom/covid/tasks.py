from datetime import datetime

from celery.schedules import crontab
from celery.task import periodic_task
from dateutil.relativedelta import relativedelta

from casexml.apps.phone.models import SyncLogSQL
from corehq.apps.formplayer_api.exceptions import FormplayerResponseException
from corehq.apps.formplayer_api.sync_db import sync_db
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import raw_username
from corehq.toggles import PRIME_FORMPLAYER_DBS
from corehq.util.celery_utils import no_result_task
from dimagi.utils.logging import notify_exception
from django.conf import settings

SYNC_CUTOFF_HOURS = 8

MIN_CASE_COUNT = 20000


@periodic_task(run_every=crontab(minute=0, hour=2), queue=settings.CELERY_PERIODIC_QUEUE)
def prime_formplayer_dbs():
    domains = PRIME_FORMPLAYER_DBS.get_enabled_domains()
    for domain in domains:
        date_cutoff = datetime.utcnow() - relativedelta(hours=SYNC_CUTOFF_HOURS)
        query = SyncLogSQL.objects.values(
            "user_id", "request_user_id"
        ).filter(
            domain=domain,
            date__gt=date_cutoff,
            is_formplayer=True,
            case_count__gt=MIN_CASE_COUNT
        ).distinct()

        for row in query.iterator():
            prime_formplayer_db_for_user.delay(domain, row["request_user_id"], row["user_id"])


@no_result_task(queue='async_restore_queue', max_retries=3, bind=True, rate_limit=50)
def prime_formplayer_db_for_user(self, domain, request_user_id, sync_user_id):
    request_user = CouchUser.get_by_user_id(request_user_id).username

    as_username = None
    if sync_user_id != request_user_id:
        as_user = CouchUser.get_by_user_id(sync_user_id)
        as_username = raw_username(as_user.username) if as_user else None

    try:
        sync_db(domain, request_user, as_username)
    except FormplayerResponseException:
        notify_exception(None, "Error while priming formplayer user DB", details={
            'domain': domain,
            'username': request_user,
            'as_user': as_username
        })
    except Exception as e:
        # most likely an error contacting formplayer, try again
        self.retry(exc=e)
