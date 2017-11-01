import re

from django.conf import settings

from casexml.apps.phone.exceptions import CouldNotPruneSyncLogs
from couchdbkit.exceptions import BulkSaveError

from dimagi.utils.couch.database import get_db


def delete_sync_logs(before_date, limit=1000, num_tries=10):
    num_deleted = 0
    for db in settings.SYNCLOGS_DBS:
        num_deleted += _delete_synclogs_from_db(db, before_date, limit, num_tries)

    return num_deleted


def _delete_synclogs_from_db(db, before_date, limit, num_tries):
    from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_synclog_ids_before_date
    from dimagi.utils.couch.database import iter_bulk_delete_with_doc_type_verification
    for i in range(num_tries):
        try:
            database = get_db(db)
            sync_log_ids = get_synclog_ids_before_date(database, before_date, limit)
            return iter_bulk_delete_with_doc_type_verification(
                database, sync_log_ids, 'SyncLog', chunksize=25)
        except BulkSaveError:
            pass

    raise CouldNotPruneSyncLogs()


ITEMS_COMMENT_PREFIX = b'<!--items='
ITESM_COMMENT_REGEX = re.compile(br'(<!--items=(\d+)-->)')


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
    match = ITESM_COMMENT_REGEX.match(cached_bytes)
    if match:
        offset = len(match.group(1))
        num_items = int(match.group(2))
        return cached_bytes[offset:], num_items
    # TODO parse and count elements in cached bytes?
    return cached_bytes, 1
