from django.conf import settings
from casexml.apps.phone.models import SyncLog
from dimagi.utils.couch.database import iter_docs


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


def get_all_sync_logs_docs():
    assert settings.UNIT_TESTING
    all_sync_log_ids = [row['id'] for row in SyncLog.view(
        "phone/sync_logs_by_user",
        reduce=False,
    )]
    return iter_docs(SyncLog.get_db(), all_sync_log_ids)
