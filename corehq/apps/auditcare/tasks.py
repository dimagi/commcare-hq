import logging
import sys

from celery.schedules import crontab
from celery.task import periodic_task
from couchdbkit.ext.django.loading import get_db

from dimagi.utils.dates import force_to_datetime
from dimagi.utils.logging import notify_exception

from corehq.apps.auditcare.models import AccessAudit, NavigationEventAudit
from corehq.apps.auditcare.utils.export import get_sql_start_date
from corehq.util.soft_assert import soft_assert

log = logging.getLogger(__name__)


@periodic_task(run_every=crontab(minute="30"), queue='background_queue')
def copy_events_to_sql(limit=1000):
    db = get_db("auditcare")
    start_date = get_sql_start_date()
    log.info(f"Initial start date: {start_date}")

    startkey = [start_date.year, start_date.month, start_date.day]
    for doc in [r["doc"] for r in db.view(
        "auditcare/all_events",
        startkey=startkey,
        reduce=False,
        include_docs=True,
        descending=True,
        limit=limit,
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
