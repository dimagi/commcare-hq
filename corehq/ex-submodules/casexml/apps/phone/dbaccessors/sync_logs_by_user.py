from casexml.apps.phone.models import SyncLogSQL, properly_wrap_sync_log


def get_synclogs_for_user(user_id, limit=10, wrap=True):
    synclogs = SyncLogSQL.objects.filter(user_id=user_id).order_by('date')[:limit]
    docs = [synclog.doc for synclog in synclogs]

    if wrap:
        return [properly_wrap_sync_log(doc) for doc in docs]
    else:
        return [doc for doc in docs]
