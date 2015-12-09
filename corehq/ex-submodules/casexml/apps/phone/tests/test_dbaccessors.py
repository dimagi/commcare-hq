import datetime
from django.test import TestCase
from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_sync_logs_for_user
from casexml.apps.phone.models import SyncLog, SimplifiedSyncLog
from corehq.util.test_utils import DocTestMixin


class DBAccessorsTest(TestCase, DocTestMixin):
    @classmethod
    def setUpClass(cls):
        cls.user_id = 'lkasdhfadsloi'
        cls.sync_logs = [
            SyncLog(user_id=cls.user_id, date=datetime.datetime(2015, 7, 1, 0, 0)),
            SimplifiedSyncLog(user_id=cls.user_id, date=datetime.datetime(2015, 3, 1, 0, 0)),
            SyncLog(user_id=cls.user_id, date=datetime.datetime(2015, 1, 1, 0, 0))
        ]
        sync_logs_other = [SyncLog(user_id='other')]
        cls.docs = cls.sync_logs + sync_logs_other
        for doc in cls.docs:
            doc.save()

    @classmethod
    def tearDownClass(cls):
        for doc in cls.docs:
            doc.delete()

    def test_get_sync_logs_for_user(self):
        self.assert_doc_lists_equal(
            get_sync_logs_for_user(self.user_id, 4), self.sync_logs)
