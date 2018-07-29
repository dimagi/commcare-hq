from __future__ import absolute_import
from casexml.apps.phone.models import SyncLogSQL
from corehq.util.test_utils import unit_testing_only


@unit_testing_only
def get_all_sync_logs_docs():
    for synclog in SyncLogSQL.objects.all():
        yield synclog.doc
