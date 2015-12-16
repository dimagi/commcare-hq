from casexml.apps.phone.models import SyncLog
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
        return SyncLog.wrap(row['doc'])
    else:
        return None


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
