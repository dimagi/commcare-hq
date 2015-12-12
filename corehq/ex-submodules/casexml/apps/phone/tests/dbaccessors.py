from casexml.apps.phone.models import SyncLog
from corehq.util.test_utils import unit_testing_only
from dimagi.utils.couch.database import iter_docs


@unit_testing_only
def get_all_sync_logs_docs():
    all_sync_log_ids = [row['id'] for row in SyncLog.view(
        "phone/sync_logs_by_user",
        reduce=False,
    )]
    return iter_docs(SyncLog.get_db(), all_sync_log_ids)
