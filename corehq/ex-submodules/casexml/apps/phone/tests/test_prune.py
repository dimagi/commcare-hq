import datetime

from django.test import TestCase

from casexml.apps.case.tests.util import delete_all_sync_logs
from freezegun import freeze_time

from casexml.apps.phone.models import (
    SimplifiedSyncLog,
    SyncLogSQL,
    properly_wrap_sync_log,
)
from casexml.apps.phone.tasks import SYNCLOG_RETENTION_DAYS, prune_synclogs

from corehq.util.test_utils import DocTestMixin


@freeze_time('2021-08-02')
class SyncLogPruneTest(TestCase, DocTestMixin):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.domain = "synclog_test"
        cls.user_id = 'sadsadsa'
        cls.docs = []
        super(SyncLogPruneTest, cls).setUpClass()
        delete_all_sync_logs()

    @classmethod
    def tearDownClass(cls):
        for doc in cls.docs:
            doc.delete()
        super(SyncLogPruneTest, cls).tearDownClass()

    def test_count_delete_queries(self):
        today = datetime.datetime.today()
        self.docs = [
            SimplifiedSyncLog(date=today - datetime.timedelta(days=SYNCLOG_RETENTION_DAYS + 7)),
            SimplifiedSyncLog(date=today - datetime.timedelta(days=SYNCLOG_RETENTION_DAYS + 1)),
            SimplifiedSyncLog(date=today - datetime.timedelta(days=SYNCLOG_RETENTION_DAYS - 7)),
        ]
        for doc in self.docs:
            doc.domain = self.domain
            doc.user_id = self.user_id
            doc.save()
        self.assert_docs_equal(self._oldest_synclog(self.user_id), self.docs[0])
        prune_synclogs()
        self.assert_docs_equal(self._oldest_synclog(self.user_id), self.docs[2])

    def _oldest_synclog(self, user_id):
        result = SyncLogSQL.objects.filter(user_id=user_id).order_by('date').first()
        if result:
            return properly_wrap_sync_log(result.doc)
