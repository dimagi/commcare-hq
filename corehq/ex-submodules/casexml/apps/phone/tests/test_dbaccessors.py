import datetime
from casexml.apps.phone.analytics import get_sync_logs_for_user, update_analytics_indexes
from dimagi.utils.couch.database import get_db
from django.test import TestCase
from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_last_synclog_for_user
from casexml.apps.phone.models import SyncLog, SimplifiedSyncLog, get_properly_wrapped_sync_log
from corehq.util.test_utils import DocTestMixin


class DBAccessorsTest(TestCase, DocTestMixin):
    dependent_apps = []
    maxDiff = None

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
        cls.legacy_sync_logs = [
            SyncLog(user_id=cls.user_id, date=datetime.datetime(2014, 12, 31, 0, 0))
        ]
        for doc in cls.legacy_sync_logs:
            get_db(None).save_doc(doc)
        update_analytics_indexes()

    @classmethod
    def tearDownClass(cls):
        for doc in cls.docs:
            doc.delete()
        get_db(None).delete_docs(cls.legacy_sync_logs)

    def test_get_sync_logs_for_user(self):
        self.assert_doc_lists_equal(
            get_sync_logs_for_user(self.user_id, 4),
            self.sync_logs + self.legacy_sync_logs)

    def test_get_last_synclog_for_user(self):
        self.assert_docs_equal(
            get_last_synclog_for_user(self.user_id), self.sync_logs[0])

    def test_get_and_save_legacy_synclog_with_attachm(self):
        legacy_sync_log = self.legacy_sync_logs[0]
        attachment_name = 'test_attach'
        get_db(None).put_attachment(legacy_sync_log._doc, 'test', attachment_name, 'text/plain')

        sync_log = get_properly_wrapped_sync_log(legacy_sync_log._id)
        self.assertIn(attachment_name, sync_log._attachments)

        # this used to fail for docs with attachments
        sync_log.save()

        # cleanup
        def del_attachment():
            get_db(None).delete_attachment(legacy_sync_log._doc, attachment_name)
            del legacy_sync_log._attachments

        self.addCleanup(del_attachment)
        self.addCleanup(sync_log.delete)
