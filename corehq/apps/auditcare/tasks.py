from celery.schedules import crontab
from celery.task import periodic_task
from couchdbkit.ext.django.loading import get_db

from corehq.apps.auditcare.models import AccessAudit, NavigationEventAudit
from corehq.apps.auditcare.utils.export import get_sql_start_date


@periodic_task(run_every=crontab(minute="30"), queue='background_queue')
def copy_events_to_sql():
    db = get_db("auditcare")
    startkey = _date_key(get_sql_start_date())
    for doc in [r["doc"] for r in db.view(
        "auditcare/all_events",
        startkey=startkey,
        reduce=False,
        include_docs=True,
        descending=True,
        limit=1000,
    )]:
        if doc["doc_type"] == "NavigationEventAudit":
            # TODO: create NavigationEventAudit in SQL
            NavigationEventAudit().save()
        elif doc["doc_type"] == "AccessAudit":
            # TODO: create AccessAudit in SQL
            AccessAudit().save()


def _date_key(date):
    return [date.year, date.month, date.day]
