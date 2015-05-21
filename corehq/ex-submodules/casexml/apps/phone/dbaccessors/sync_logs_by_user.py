from casexml.apps.phone.models import SyncLog


def get_last_synclog_for_user(user_id):
    return SyncLog.view(
        "phone/sync_logs_by_user",
        startkey=[user_id, {}],
        endkey=[user_id],
        descending=True,
        limit=1,
        reduce=False,
        include_docs=True,
    ).one()
