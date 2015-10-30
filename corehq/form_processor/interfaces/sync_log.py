from casexml.apps.phone.models import SyncLog

from ..utils import to_generic


class SyncLogInterface(object):

    @staticmethod
    @to_generic
    def create_from_generic(generic_sync_log, generic_attachment=None):
        sync_log = SyncLog.from_generic(generic_sync_log)
        sync_log.save()
        return sync_log
