from __future__ import absolute_import
import datetime

from django.test import TestCase

from casexml.apps.phone.analytics import get_sync_logs_for_user, update_analytics_indexes
from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_last_synclog_for_user
from casexml.apps.phone.models import SyncLog, SimplifiedSyncLog
from corehq.util.test_utils import DocTestMixin


class DBAccessorsTest(TestCase, DocTestMixin):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(DBAccessorsTest, cls).setUpClass()
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
        update_analytics_indexes()

    @classmethod
    def tearDownClass(cls):
        for doc in cls.docs:
            doc.delete()
        super(DBAccessorsTest, cls).tearDownClass()

    def test_get_sync_logs_for_user(self):
        self.assert_doc_sets_equal(get_sync_logs_for_user(self.user_id, 4), self.sync_logs)

    def test_get_last_synclog_for_user(self):
        self.assert_docs_equal(get_last_synclog_for_user(self.user_id), self.sync_logs[0])
