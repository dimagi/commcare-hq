from datetime import datetime

from django.test import TestCase

from casexml.apps.phone.models import SyncLogSQL, SimplifiedSyncLog


class SyncLogQueryTest(TestCase):

    def tearDown(self):
        SyncLogSQL.objects.all().delete()
        super().tearDown()

    def _count(self):
        return SyncLogSQL.objects.count()

    def test_simple(self):
        synclog = SimplifiedSyncLog(domain='test', user_id='user1', date=datetime(2015, 7, 1, 0, 0))
        synclog.save()
        self.assertEqual(self._count(), 1)
        synclog.delete()
        self.assertEqual(self._count(), 0)

    def test_update(self):
        synclog = SimplifiedSyncLog(domain='test', user_id='user1', date=datetime(2015, 7, 1, 0, 0))
        synclog.save()

        with self.assertNumQueries(1):
            # previously this was 2 queries, fetch + update
            synclog.save()
