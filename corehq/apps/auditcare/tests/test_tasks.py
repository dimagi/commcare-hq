from datetime import datetime

from ..models import AccessAudit, NavigationEventAudit
from ..tasks import copy_events_to_sql
from .testutils import AuditcareTest, delete_couch_docs, save_couch_doc


class TestCopyEventsToSQL(AuditcareTest):
    username = "audit@care.com"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        username = "couch@test.com"
        cls.couch_ids = [
            save_couch_doc(
                "NavigationEventAudit",
                username,
                event_date=datetime(2021, 2, 1, 2).strftime("%Y-%m-%dT%H:%M:%SZ"),
                description='User Name',
                extra={},
                headers={
                    'REQUEST_METHOD': 'GET',
                },
                ip_address='10.1.2.3',
                request_path='/a/delmar/phone/restore/?version=2.0&since=...',
                session_key='abc123',
                status_code=200,
                user_agent='okhttp/4.4.1',
                view_kwargs={'domain': 'delmar'},
                view='corehq.apps.ota.views.restore',
            ),
            save_couch_doc(
                "AccessAudit",
                username,
                event_date=datetime(2021, 2, 1, 3).strftime("%Y-%m-%dT%H:%M:%SZ"),
                access_type='login',
                description='Login Success',
                failures_since_start=None,
                get_data=[],
                http_accept='text/html',
                ip_address='10.1.3.2',
                path_info='/a/delmar/login/',
                post_data=[],
                session_key='abc123',
                user_agent='Mozilla/5.0',
            ),
            save_couch_doc(
                "NavigationEventAudit",
                username,
                event_date=datetime(2021, 2, 1, 5).strftime("%Y-%m-%dT%H:%M:%SZ"),
                description='User Name',
                extra={},
                headers={
                    'REQUEST_METHOD': 'GET',
                },
                ip_address='10.1.2.3',
                request_path='/a/sandwich/phone/restore/?version=2.0&since=...',
                session_key='abc123',
                status_code=200,
                user_agent='okhttp/4.4.1',
                view_kwargs={'domain': 'sandwich'},
                view='corehq.apps.ota.views.restore',
            ),
        ]

    @classmethod
    def tearDownClass(cls):
        delete_couch_docs(cls.couch_ids)
        super().tearDownClass()

    def test_copy(self):

        def _assert():
            self.assertEqual(NavigationEventAudit.objects.count(), 2)
            self.assertEqual(
                [e.path for e in NavigationEventAudit.objects.order_by("-event_date").all()],
                ["just/a/checkpoint", "/a/delmar/phone/restore/"]
            )
            self.assertEqual(
                [e.params for e in NavigationEventAudit.objects.order_by("-event_date").all()],
                ["", "version=2.0&since=..."]
            )
            self.assertEqual(AccessAudit.objects.count(), 1)
            self.assertEqual(AccessAudit.objects.first().path, "/a/delmar/login/")

        NavigationEventAudit(event_date=datetime(2021, 2, 1, 4), path="just/a/checkpoint").save()
        copy_events_to_sql()
        _assert()

        # Re-copying should have no effect
        copy_events_to_sql()
        _assert()

    def test_limit(self):
        NavigationEventAudit(event_date=datetime(2021, 2, 1, 4), path="just/a/checkpoint").save()
        copy_events_to_sql(limit=1)
        self.assertEqual(NavigationEventAudit.objects.count(), 1)
        self.assertEqual(NavigationEventAudit.objects.first().path, "just/a/checkpoint")

        self.assertEqual(AccessAudit.objects.count(), 1)
        self.assertEqual(AccessAudit.objects.first().path, "/a/delmar/login/")
