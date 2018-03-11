from __future__ import absolute_import
import datetime

from django.test import TestCase

from casexml.apps.case.tests.util import delete_all_sync_logs
from casexml.apps.phone.analytics import update_analytics_indexes
from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_last_synclog_for_user, get_synclogs_for_user
from casexml.apps.phone.models import SyncLog, SyncLogSQL, SimplifiedSyncLog, delete_synclog
from casexml.apps.phone.exceptions import MissingSyncLog
from corehq.util.test_utils import DocTestMixin


class DBAccessorsTest(TestCase, DocTestMixin):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        domain = "synclog_test"
        super(DBAccessorsTest, cls).setUpClass()
        delete_all_sync_logs()
        cls.user_id = 'lkasdhfadsloi'
        cls.sync_logs = [
            SyncLog(domain=domain, user_id=cls.user_id, date=datetime.datetime(2015, 7, 1, 0, 0)),
            SimplifiedSyncLog(domain=domain, user_id=cls.user_id, date=datetime.datetime(2015, 3, 1, 0, 0)),
            SyncLog(domain=domain, user_id=cls.user_id, date=datetime.datetime(2015, 1, 1, 0, 0))
        ]
        sync_logs_other = [SyncLog(domain=domain, user_id='other')]
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
        self.assert_doc_sets_equal(get_synclogs_for_user(self.user_id, 4), self.sync_logs)

    def test_get_last_synclog_for_user(self):
        self.assert_docs_equal(get_last_synclog_for_user(self.user_id), self.sync_logs[0])


class SyncLogQueryTest(TestCase):
    def _sql_count(self):
        return SyncLogSQL.objects.count()

    def _couch_count(self):
        return len(SyncLog.view("phone/sync_logs_by_user", include_docs=False).all())

    def test_default(self):
        synclog = SyncLog(domain='test', user_id='user1', date=datetime.datetime(2015, 7, 1, 0, 0))
        synclog.save()
        self.assertEqual(self._sql_count(), 1)
        self.assertEqual(self._couch_count(), 0)

        delete_synclog(synclog._id)
        self.assertEqual(self._sql_count(), 0)
        self.assertEqual(self._couch_count(), 0)

    def test_couch_synclogs(self):
        synclog = SyncLog(domain='test', user_id='user1', date=datetime.datetime(2015, 7, 1, 0, 0))
        SyncLog.get_db().save_doc(synclog)
        self.assertEqual(self._sql_count(), 0)
        self.assertEqual(self._couch_count(), 1)

        delete_synclog(synclog._id)
        self.assertEqual(self._sql_count(), 0)
        self.assertEqual(self._couch_count(), 0)

        with self.assertRaises(MissingSyncLog):
            delete_synclog(synclog._id)
