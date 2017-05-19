from casexml.apps.phone.models import SyncLog, properly_wrap_sync_log


def get_last_synclog_for_user(user_id):
    result = SyncLog.view(
        "phone/sync_logs_by_user",
        startkey=[user_id, {}],
        endkey=[user_id],
        descending=True,
        limit=1,
        reduce=False,
        include_docs=True,
        wrap_doc=False
    )
    if result:
        row, = result
        return properly_wrap_sync_log(row['doc'])


def get_synclogs_for_user(user_id, limit=10):
    result = SyncLog.view(
        "phone/sync_logs_by_user",
        startkey=[user_id, {}],
        endkey=[user_id],
        descending=True,
        limit=limit,
        reduce=False,
        include_docs=True,
        wrap_doc=False
    )
    return result
