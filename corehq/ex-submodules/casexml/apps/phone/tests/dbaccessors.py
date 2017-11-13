from __future__ import absolute_import
from casexml.apps.phone.dbaccessors.sync_logs_by_user import synclog_view
from casexml.apps.phone.models import SyncLog
from corehq.util.test_utils import unit_testing_only
from dimagi.utils.couch.database import iter_docs


@unit_testing_only
def get_all_sync_logs_docs():
    return [row['doc'] for row in synclog_view(
        "phone/sync_logs_by_user",
        reduce=False,
    )]
