from casexml.apps.phone.models import SyncLog

def get_last_synclogs_for_user(user_id):
    result = SyncLog.view(
        "phone/sync_logs_by_user",
        startkey=[user_id, {}],
        endkey=[user_id],
        descending=True,
        limit=10,
        reduce=False,
        include_docs=True,
        wrap_doc=False
    )
    return result