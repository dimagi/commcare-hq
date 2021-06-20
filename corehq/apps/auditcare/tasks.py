import logging

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
from corehq.util.soft_assert import soft_assert
from corehq.apps.auditcare.utils.migration import AuditCareMigrationUtil, get_formatted_datetime_string

log = logging.getLogger(__name__)

ACCESS_LOOKUP = {
    "login": ACCESS_LOGIN,
    "logout": ACCESS_LOGOUT,
    "login_failed": ACCESS_FAILED,
}


def get_couch_key(time):
    return [time.year, time.month, time.day, time.hour, time.minute, time.second]


def get_migration_key(start_time, end_time):
    return get_formatted_datetime_string(start_time) + '_' + get_formatted_datetime_string(end_time)


def copy_events_to_sql(start_time, end_time, retry=0):
    db = get_db("auditcare")
    util = AuditCareMigrationUtil()
    log.info(f"Starting batch: {start_time} - {end_time}")
    print(f"Starting batch: {start_time} - {end_time}")
    key = get_migration_key(start_time, end_time)
    endkey = get_couch_key(end_time)
    startkey = get_couch_key(start_time)
    util.log_batch_start(key)
    count = 0
    is_errored = False
    for result in db.view(
        "auditcare/all_events",
        startkey=startkey,
        endkey=endkey,
        reduce=False,
        include_docs=True,
    ):
        doc = result["doc"]
        try:
            kwargs = _pick(doc, ["user", "domain", "ip_address", "session_key",
                                 "headers", "status_code", "user_agent"])
            kwargs.update({
                "event_date": force_to_datetime(doc.get("event_date")),
                "couch_id": doc["_id"],
            })

            if doc["doc_type"] == "NavigationEventAudit":
                if NavigationEventAudit.objects.filter(couch_id=doc["_id"]).exists():
                    continue
                kwargs.update(_pick(doc, ["headers", "status_code", "view", "view_kwargs"]))
                path, _, params = doc.get("request_path", "").partition("?")
                kwargs.update({
                    "path": path,
                    "params": params,
                })
                NavigationEventAudit(**kwargs).save()
            elif doc["doc_type"] == "AccessAudit":
                if AccessAudit.objects.filter(couch_id=doc["_id"]).exists():
                    continue
                kwargs.update(_pick(doc, ["http_accept", "trace_id"]))
                access_type = doc.get('access_type')
                kwargs.update({
                    "access_type": ACCESS_LOOKUP.get(doc.get("access_type")),
                    "path": doc.get("path_info"),
                })
                if access_type == "logout":
                    kwargs.update({"path": "accounts/logout"})
                AccessAudit(**kwargs).save()
            count += 1

        except Exception:
            copy_events_to_sql(start_time, end_time, retry + 1)
            if retry >= 3:
                is_errored = True
                message = f"Error in copy_events_to_sql on doc {doc['_id']}"
                notify_exception(None, message=message)
                _soft_assert = soft_assert(to="{}@{}.com".format('aphulera', 'dimagi'), notify_admins=False)
                _soft_assert(False, message)
                break
    if is_errored:
        util.set_batch_as_errored(key)
    else:
        util.set_batch_as_finished(key, count)


def _pick(doc, keys):
    return {key: doc.get(key) for key in keys if doc.get(key)}
