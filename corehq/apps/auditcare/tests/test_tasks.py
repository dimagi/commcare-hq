from datetime import datetime

from ..models import AccessAudit, NavigationEventAudit
from ..tasks import copy_events_to_sql
from ..tests.data.auditcare_migration import task_docs
from .testutils import AuditcareTest, delete_couch_docs, save_couch_doc


class TestCopyEventsToSQL(AuditcareTest):
    username = "audit@care.com"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.couch_ids = [save_couch_doc(**doc) for doc in task_docs]

    @classmethod
    def tearDownClass(cls):
        delete_couch_docs(cls.couch_ids)
        super().tearDownClass()

    def test_copy(self):
        def _assert():
            self.assertEqual(NavigationEventAudit.objects.count(), 3)
            self.assertEqual(
                [e.path for e in NavigationEventAudit.objects.order_by("-event_date").all()],
                ["just/a/checkpoint", '/a/random/phone/restore/', '/a/test-space/phone/restore/']
            )
            self.assertEqual(
                [e.params for e in NavigationEventAudit.objects.order_by("-event_date").all()],
                ["", "version=2.0&since=...", "version=2.0&since=..."]
            )
            self.assertEqual(AccessAudit.objects.count(), 1)
            self.assertEqual(AccessAudit.objects.first().path, "/a/delmar/login/")

        NavigationEventAudit(event_date=datetime(2021, 2, 1, 4), path="just/a/checkpoint").save()
        copy_events_to_sql(start_time=datetime(2021, 2, 1, 2), end_time=datetime(2021, 2, 1, 5))
        _assert()

        # Re-copying should have no effect
        copy_events_to_sql(start_time=datetime(2021, 2, 1, 2), end_time=datetime(2021, 2, 1, 5))
        _assert()
