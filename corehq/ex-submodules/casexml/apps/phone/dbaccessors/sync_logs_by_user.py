from __future__ import absolute_import
from datetime import date
from casexml.apps.phone.exceptions import CouldNotRetrieveSyncLogIds
from casexml.apps.phone.models import SyncLog, SyncLogSQL, properly_wrap_sync_log
from restkit.errors import RequestFailed
from six.moves import range


def get_last_synclog_for_user(user_id):
    result = SyncLogSQL.objects.filter(user_id=user_id).order_by('date').last()
    return properly_wrap_sync_log(result.doc) if result else None


def get_synclogs_for_user(user_id, limit=10, wrap=True):
    synclogs = SyncLogSQL.objects.filter(user_id=user_id, limit=10)
    if wrap:
        return [properly_wrap_sync_log(synclog.doc) for synclog in synclogs]
    else:
        return [synclog.doc for synclog in synclogs]


def get_synclog_ids_before_date(before_date, limit=1000, num_tries=10):
    if isinstance(before_date, date):
        before_date = before_date.strftime("%Y-%m-%d")

    for i in range(num_tries):
        try:
            return [r['id'] for r in SyncLog.view(
                "sync_logs_by_date/view",
                endkey=[before_date],
                limit=limit,
                reduce=False,
                include_docs=False
            )]
        except RequestFailed:
            pass

    raise CouldNotRetrieveSyncLogIds()
