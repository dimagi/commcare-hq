from couchdbkit import ResourceNotFound

from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.models import SyncLog
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import safe_delete
from corehq.util.test_utils import unit_testing_only


class FormProcessorTestUtils(object):

    @classmethod
    @unit_testing_only
    def delete_all_cases(cls):
        cls._delete_all(CommCareCase.get_db(), 'case/get_lite')

    @classmethod
    @unit_testing_only
    def delete_all_xforms(cls):
        cls._delete_all(XFormInstance.get_db(), 'couchforms/all_submissions_by_domain')

    @classmethod
    @unit_testing_only
    def delete_all_sync_logs(cls):
        cls._delete_all(SyncLog.get_db(), 'phone/sync_logs_by_user')

    @staticmethod
    @unit_testing_only
    def _delete_all(db, viewname):
        deleted = set()
        for row in db.view(viewname, reduce=False):
            doc_id = row['id']
            if id not in deleted:
                try:
                    safe_delete(db, doc_id)
                    deleted.add(doc_id)
                except ResourceNotFound:
                    pass
