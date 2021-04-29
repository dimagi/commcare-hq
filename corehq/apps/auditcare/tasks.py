from dimagi.utils.dates import force_to_datetime
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
        try:
            kwargs = _pick(doc, ["user", "domain", "path", "ip_address", "session_key",
                                 "headers", "status_code", "user_agent"])
            kwargs.update({
                "event_date": force_to_datetime(doc.get("event_date")),
                "path": doc.get("request_path"),
            })
            if doc["doc_type"] == "NavigationEventAudit":
                kwargs.update(_pick(doc, ["params", "headers", "status_code", "view", "view_kwargs"]))
                NavigationEventAudit(**kwargs).save()
            elif doc["doc_type"] == "AccessAudit":
                kwargs.update(_pick(doc, ["http_accept", "access_type", "trace_id"]))
                AccessAudit().save()
        except Exception:
            message = f"Error in copy_events_to_sql on doc {doc['_id']}"
            notify_exception(None, message=message)
            _soft_assert = soft_assert(to="{}@{}.com".format('jschweers', 'dimagi'), notify_admins=False)
            _soft_assert(False, message)
            sys.exit(1)

    final_start_date = get_sql_start_date()
    log.info(f"Final start date: {final_start_date}")


def _pick(doc, keys):
    return {key: doc.get(key) for key in keys if doc.get(key)}
