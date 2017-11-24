from __future__ import absolute_import
from builtins import range
from datetime import date
from casexml.apps.phone.exceptions import CouldNotRetrieveSyncLogIds
from casexml.apps.phone.models import SyncLog, properly_wrap_sync_log
from restkit.errors import RequestFailed


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
