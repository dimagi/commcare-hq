from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.phone.models import SyncLog


def update_analytics_indexes():
    SyncLog.view("phone/sync_logs_by_user", limit=1, reduce=False)
