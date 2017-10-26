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


ITEMS_COMMENT_PREFIX = b'<!--items='


def get_cached_items_with_count(cached_bytes):
    """Get the number of items encoded in cached XML elements byte string

    The string, if it contains an item count, should be prefixed with
    b'<!--items=' followed by one or more numeric digits (0-9), then
    b'-->', and finally the cached XML elements.

    Example: b'<!--items=42--><fixture>...</fixture>'

    If the string does not start with b'<!--items=' then it is assumed
    to contain only XML elements.

    :returns: Two-tuple: (xml_elements_bytes, num_items)
    """
    if cached_bytes.startswith(ITEMS_COMMENT_PREFIX):
        DIGITS = b'0123456789'
        digits = []
        i = len(ITEMS_COMMENT_PREFIX)
        total_bytes = len(cached_bytes)
        while i < total_bytes and cached_bytes[i] in DIGITS:
            digits.append(cached_bytes[i])
            i += 1
        if digits and cached_bytes[i:i + 3] == b'-->':
            num_items = int(b"".join(digits))
            return cached_bytes[i + 3:], num_items
    # TODO parse and count elements in cached bytes?
    return cached_bytes, 1
