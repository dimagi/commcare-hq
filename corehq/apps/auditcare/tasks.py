import logging
import sys

from celery.schedules import crontab
from celery.task import periodic_task
from couchdbkit.ext.django.loading import get_db

from dimagi.utils.dates import force_to_datetime
from dimagi.utils.logging import notify_exception

from corehq.apps.auditcare.models import (
    ACCESS_LOGIN,
    ACCESS_LOGOUT,
    ACCESS_FAILED,
    AccessAudit,
    NavigationEventAudit,
)
from corehq.apps.auditcare.utils.export import get_sql_start_date
from corehq.util.soft_assert import soft_assert

log = logging.getLogger(__name__)

ACCESS_LOOKUP = {
    "login": ACCESS_LOGIN,
    "logout": ACCESS_LOGOUT,
    "login_failed": ACCESS_FAILED,
}


@periodic_task(run_every=crontab(minute="30"), queue='background_queue')
def copy_events_to_sql(limit=1000):
    db = get_db("auditcare")
    start_date = get_sql_start_date()
    log.info(f"Initial start date: {start_date}")

    startkey = [
        start_date.year,
        start_date.month,
        start_date.day,
        start_date.hour,
        start_date.minute,
        start_date.second,
        start_date.microsecond,
    ]
    for doc in [r["doc"] for r in db.view(
        "auditcare/all_events",
        startkey=startkey,
        reduce=False,
        include_docs=True,
        descending=True,
        limit=limit,
    )]:
        try:
            kwargs = _pick(doc, ["user", "domain", "ip_address", "session_key",
                                 "headers", "status_code", "user_agent"])
            kwargs.update({
                "event_date": force_to_datetime(doc.get("event_date")),
            })
            if doc["doc_type"] == "NavigationEventAudit":
                kwargs.update(_pick(doc, ["params", "headers", "status_code", "view", "view_kwargs"]))
                kwargs.update({
                    "path": doc.get("request_path"),
                })
                NavigationEventAudit(**kwargs).save()
            elif doc["doc_type"] == "AccessAudit":
                kwargs.update(_pick(doc, ["http_accept", "trace_id"]))
                kwargs.update({
                    "access_type": ACCESS_LOOKUP.get(doc.get("access_type")),
                    "path": doc.get("path_info"),
                })
                AccessAudit(**kwargs).save()
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
