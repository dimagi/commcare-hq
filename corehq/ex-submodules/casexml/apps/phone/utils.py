from corehq.toggles import BLOBDB_RESTORE


def get_restore_response_class(domain):
    from casexml.apps.phone.restore import BlobRestoreResponse, FileRestoreResponse

    if BLOBDB_RESTORE.enabled(domain):
        return BlobRestoreResponse
    return FileRestoreResponse


def delete_sync_logs(before_date, limit=1000):
    from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_synclog_ids_before_date
    from casexml.apps.phone.models import SyncLog
    from dimagi.utils.couch.database import iter_bulk_delete_with_doc_type_verification
    sync_log_ids = get_synclog_ids_before_date(before_date, limit)
    return iter_bulk_delete_with_doc_type_verification(SyncLog.get_db(), sync_log_ids, 'SyncLog', chunksize=5)
