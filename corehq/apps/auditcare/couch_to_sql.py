import logging

from couchdbkit.ext.django.loading import get_db

from dimagi.utils.couch.database import retry_on_couch_error
from dimagi.utils.dates import force_to_datetime
from dimagi.utils.logging import notify_exception

from corehq.apps.auditcare.models import (
    ACCESS_FAILED,
    ACCESS_LOGIN,
    ACCESS_LOGOUT,
    AccessAudit,
    NavigationEventAudit,
)
from corehq.apps.auditcare.utils.migration import (
    AuditCareMigrationUtil,
    get_formatted_datetime_string,
)
from corehq.util.soft_assert import soft_assert

logger = logging.getLogger(__name__)
logger.setLevel('INFO')

ACCESS_LOOKUP = {
    "login": ACCESS_LOGIN,
    "logout": ACCESS_LOGOUT,
    "login_failed": ACCESS_FAILED,
}

COUCH_QUERY_LIMIT = 1000


def get_couch_key(time):
    if not time:
        return
    return [time.year, time.month, time.day, time.hour, time.minute, time.second]


def get_migration_key(start_time, end_time):
    return get_formatted_datetime_string(start_time) + '_' + get_formatted_datetime_string(end_time)


@retry_on_couch_error
def _get_couch_docs(start_key, end_key):
    db = get_db("auditcare")
    result = db.view(
        "auditcare/all_events",
        startkey=start_key,
        endkey=end_key,
        reduce=False,
        include_docs=True,
        descending=True,
        limit=COUCH_QUERY_LIMIT
    )
    return list(result)


def get_unsaved_events(nav_objs, access_objs, nav_couch_ids, access_couch_ids):
    existing_access_events = set(AccessAudit.objects.filter(
        couch_id__in=access_couch_ids
    ).values_list('couch_id', flat=True))
    existing_nav_events = set(NavigationEventAudit.objects.filter(
        couch_id__in=nav_couch_ids
    ).values_list('couch_id', flat=True))

    final_nav_events = ([
        nav_obj for nav_obj in nav_objs
        if nav_obj.couch_id not in existing_nav_events
    ])

    final_access_events = ([
        access_obj for access_obj in access_objs
        if access_obj.couch_id not in existing_access_events
    ])
    return {
        "navigation_events": final_nav_events,
        "audit_events": final_access_events,
        "count": len(final_nav_events) + len(final_access_events)
    }


def get_events_from_couch(start_key, end_key):
    navigation_objects = []
    access_objects = []
    records_returned = 0
    next_start_time = None
    nav_couch_ids = []
    access_couch_ids = []
    couch_docs = _get_couch_docs(start_key, end_key)
    for result in couch_docs:
        records_returned += 1
        doc = result["doc"]
        next_start_time = force_to_datetime(doc.get("event_date"))
        kwargs = _pick(doc, ["user", "domain", "ip_address", "session_key",
                            "status_code", "user_agent"])
        kwargs.update({
            "event_date": next_start_time,
            "couch_id": doc["_id"],
        })

        if doc["doc_type"] == "NavigationEventAudit":
            nav_couch_ids.append(doc['_id'])
            kwargs.update(_pick(doc, ["headers", "status_code", "view", "view_kwargs"]))
            path, _, params = doc.get("request_path", "").partition("?")
            kwargs.update({
                "path": path,
                "params": params,
            })
            navigation_objects.append(NavigationEventAudit(**kwargs))
        elif doc["doc_type"] == "AccessAudit":
            access_couch_ids.append(doc['_id'])
            kwargs.update(_pick(doc, ["http_accept", "trace_id"]))
            access_type = doc.get('access_type')
            kwargs.update({
                "access_type": ACCESS_LOOKUP.get(doc.get("access_type")),
                "path": doc.get("path_info"),
            })
            if access_type == "logout":
                kwargs.update({"path": "accounts/logout"})
            access_objects.append(AccessAudit(**kwargs))

    res_obj = get_unsaved_events(
        navigation_objects,
        access_objects,
        nav_couch_ids,
        access_couch_ids
    )

    res_obj.update({
        "break_query": records_returned < COUCH_QUERY_LIMIT or not next_start_time,
        "next_start_key": get_couch_key(next_start_time),
    })
    return res_obj


def copy_events_to_sql(start_time, end_time):
    util = AuditCareMigrationUtil()
    logger.info(f"Starting batch: {start_time} - {end_time}")
    key = get_migration_key(start_time, end_time)
    end_key = get_couch_key(end_time)
    start_key = get_couch_key(start_time)
    next_start_key = start_key
    util.log_batch_start(key)
    break_query = False
    count = 0
    try:
        while not break_query:
            events_info = get_events_from_couch(next_start_key, end_key)
            next_start_key = events_info['next_start_key']
            NavigationEventAudit.objects.bulk_create(events_info['navigation_events'], ignore_conflicts=True)
            AccessAudit.objects.bulk_create(events_info['audit_events'], ignore_conflicts=True)
            count += events_info['count']
            break_query = events_info['break_query']
    except Exception as e:
        message = f"""Error in copy_events_to_sql in key {key}
            Next start key is {next_start_key}
            {e}"""
        util.set_batch_as_errored(key)
        notify_exception(None, message=message)
        _soft_assert = soft_assert(to="{}@{}.com".format('aphulera', 'dimagi'), notify_admins=False)
        _soft_assert(False, message)
        return
    logger.info(f"Batch finished: {start_time} - {end_time}")
    util.set_batch_as_finished(key, count)


def _pick(doc, keys):
    return {key: doc.get(key) for key in keys if doc.get(key)}
