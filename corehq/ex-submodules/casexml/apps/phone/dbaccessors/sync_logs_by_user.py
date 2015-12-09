from django.conf import settings
from casexml.apps.phone.models import SyncLog, properly_wrap_sync_log
from dimagi.utils.couch.database import iter_docs, get_db


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


def get_sync_logs_for_user(user_id, limit):
    rows = combine_views(
        [SyncLog.get_db(), get_db(None)],
        "phone/sync_logs_by_user",
        startkey=[user_id, {}],
        endkey=[user_id],
        descending=True,
        reduce=False,
        limit=limit,
        include_docs=True,
    )
    sync_log_jsons = (row['doc'] for row in rows)
    return [properly_wrap_sync_log(sync_log_json) for sync_log_json in sync_log_jsons]


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
