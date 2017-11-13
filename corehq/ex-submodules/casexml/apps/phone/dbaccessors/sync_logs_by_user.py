from __future__ import absolute_import
from datetime import date

from django.conf import settings
from restkit.errors import RequestFailed

from casexml.apps.phone.exceptions import CouldNotRetrieveSyncLogIds
from casexml.apps.phone.models import properly_wrap_sync_log
from dimagi.utils.couch.database import get_db


def get_last_synclog_for_user(user_id):
    results = synclog_view(
        "phone/sync_logs_by_user",
        startkey=[user_id, {}],
        endkey=[user_id],
        descending=True,
        limit=1,
        reduce=False,
        include_docs=True,
    )
    if results:
        row, = results
        return properly_wrap_sync_log(row['doc'])
    else:
        return None


def synclog_view(view_name, **params):
    return combine_views(synclog_dbs(), view_name, **params)


def synclog_dbs():
    return [
        get_db(prefix) for prefix in settings.SYNCLOGS_DBS
    ]


def combine_views(dbs, view_name, **params):
    assert params.get('reduce') is False, 'You must call combine_views with reduce=False'
    assert not params.get('skip'), 'You cannot call combine_views with skip'
    rows = []
    for db in dbs:
        rows.extend(db.view(view_name, **params))

    if params.get('descending'):
        rows.sort(key=lambda row: row['key'], reverse=True)
    else:
        rows.sort(key=lambda row: row['key'])

    if 'limit' in params:
        return rows[:params['limit']]
    else:
        return rows


def get_synclogs_for_user(user_id, limit=10, wrap=True):
    results = synclog_view(
        "phone/sync_logs_by_user",
        startkey=[user_id, {}],
        endkey=[user_id],
        descending=True,
        limit=limit,
        reduce=False,
        include_docs=True,
    )

    sync_log_docs = [row['doc'] for row in results]
    if wrap:
        return [properly_wrap_sync_log(sync_log_json) for sync_log_json in sync_log_docs]
    else:
        return sync_log_docs


def update_synclog_indexes():
    synclog_view("phone/sync_logs_by_user", limit=1, reduce=False)


def get_synclog_ids_before_date(db, before_date, limit=1000, num_tries=10):
    if isinstance(before_date, date):
        before_date = before_date.strftime("%Y-%m-%d")

    for i in range(num_tries):
        try:
            return [r['id'] for r in db.view(
                "sync_logs_by_date/view",
                endkey=[before_date],
                limit=limit,
                reduce=False,
                include_docs=False
            )]
        except RequestFailed:
            pass

    raise CouldNotRetrieveSyncLogIds()
