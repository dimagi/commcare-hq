from casexml.apps.phone.dbaccessors.sync_logs_by_user import synclog_view
from casexml.apps.phone.models import properly_wrap_sync_log
from corehq.util.couch import stale_ok


def update_analytics_indexes():
    synclog_view("phone/sync_logs_by_user", limit=1, reduce=False)


def get_sync_logs_for_user(user_id, limit):
    rows = synclog_view(
        "phone/sync_logs_by_user",
        startkey=[user_id, {}],
        endkey=[user_id],
        descending=True,
        reduce=False,
        limit=limit,
        include_docs=True,
        stale=stale_ok()
    )
    sync_log_jsons = (row['doc'] for row in rows)
    return [properly_wrap_sync_log(sync_log_json) for sync_log_json in sync_log_jsons]
