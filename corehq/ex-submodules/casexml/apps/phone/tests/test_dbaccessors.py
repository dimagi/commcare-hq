from __future__ import absolute_import
import datetime

from django.conf import settings

from casexml.apps.case.tests.util import delete_all_sync_logs
from dimagi.utils.couch.database import get_db
from django.test import TestCase
from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_last_synclog_for_user, get_synclogs_for_user, \
    update_synclog_indexes, get_synclog_ids_before_date
from casexml.apps.phone.models import SyncLog, SimplifiedSyncLog
from corehq.util.test_utils import DocTestMixin


class DBAccessorsTest(TestCase, DocTestMixin):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(DBAccessorsTest, cls).setUpClass()
        delete_all_sync_logs()
        cls.user_id = 'lkasdhfadsloi'
        cls.sync_logs = [
            SyncLog(user_id=cls.user_id, date=datetime.datetime(2015, 7, 1, 0, 0)),
            SimplifiedSyncLog(user_id=cls.user_id, date=datetime.datetime(2015, 3, 1, 0, 0)),
            SyncLog(user_id=cls.user_id, date=datetime.datetime(2015, 2, 1, 0, 0))
        ]
        sync_logs_other = [SyncLog(user_id='other', date=datetime.datetime(2015, 1, 1, 0, 0))]
        cls.docs = cls.sync_logs + sync_logs_other
        for doc in cls.docs:
            doc.save()
        cls.legacy_sync_logs = [
            SyncLog(user_id=cls.user_id, date=datetime.datetime(2014, 12, 31, 0, 0))
        ]
        for doc in cls.legacy_sync_logs:
            get_db(settings.SYNCLOGS_OLD_DB).save_doc(doc)
        update_synclog_indexes()

    @classmethod
    def tearDownClass(cls):
        for doc in cls.docs:
            doc.delete()
        get_db(settings.SYNCLOGS_OLD_DB).delete_docs(cls.legacy_sync_logs)
        super(DBAccessorsTest, cls).tearDownClass()

    def test_get_synclogs_for_user(self):
        self.assert_doc_sets_equal(
            get_synclogs_for_user(self.user_id, 4),
            self.sync_logs + self.legacy_sync_logs)

    def test_get_last_synclog_for_user(self):
        self.assert_docs_equal(
            get_last_synclog_for_user(self.user_id), self.sync_logs[0])

    def test_get_synclog_ids_before_date(self):
        doc_ids = get_synclog_ids_before_date(SyncLog.get_db(), datetime.datetime.utcnow())
        self.assertEqual(doc_ids, [
            log._id for log in reversed(self.docs)
        ])

        doc_ids = get_synclog_ids_before_date(get_db(settings.SYNCLOGS_OLD_DB), datetime.datetime.utcnow())
        self.assertEqual(doc_ids, [
            log._id for log in self.legacy_sync_logs
        ])
