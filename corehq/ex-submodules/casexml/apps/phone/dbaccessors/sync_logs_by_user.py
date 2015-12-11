from django.conf import settings

from casexml.apps.phone.models import SyncLog
from dimagi.utils.couch.database import iter_docs, get_db


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
        return SyncLog.wrap(row['doc'])
    else:
        return None


def get_all_sync_logs_docs():
    assert settings.UNIT_TESTING
    all_sync_log_ids = [row['id'] for row in SyncLog.view(
        "phone/sync_logs_by_user",
        reduce=False,
    )]
    return iter_docs(SyncLog.get_db(), all_sync_log_ids)


def synclog_view(view_name, **params):
    return combine_views([SyncLog.get_db(), get_db(None)], view_name, **params)


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
