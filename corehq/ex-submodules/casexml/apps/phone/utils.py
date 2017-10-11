from casexml.apps.phone.exceptions import CouldNotPruneSyncLogs
from couchdbkit.exceptions import BulkSaveError


def delete_sync_logs(before_date, limit=1000, num_tries=10):
    from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_synclog_ids_before_date
    from casexml.apps.phone.models import SyncLog
    from dimagi.utils.couch.database import iter_bulk_delete_with_doc_type_verification

    for i in range(num_tries):
        try:
            sync_log_ids = get_synclog_ids_before_date(before_date, limit)
            return iter_bulk_delete_with_doc_type_verification(SyncLog.get_db(), sync_log_ids, 'SyncLog', chunksize=25)
        except BulkSaveError:
            pass

    raise CouldNotPruneSyncLogs()
