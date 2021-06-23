import os.path
from contextlib import contextmanager
from csv import DictReader
from datetime import datetime
from itertools import chain
from unittest.mock import patch

from testil import tempdir

from corehq.apps.auditcare.models import AccessAudit, NavigationEventAudit

from ..utils.export import (
    AuditWindowQuery,
    ForeignKeyAccessError,
    get_all_log_events,
    get_foreign_names,
    get_sql_start_date,
    navigation_events_by_user,
    write_export_from_all_log_events,
)
from .testutils import AuditcareTest, save_couch_doc, delete_couch_docs


class TestNavigationEventsQueries(AuditcareTest):

    maxDiff = None
    username = "test@test.com"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        username = "couch@test.com"
        event_date = datetime(2021, 2, 1, 2).strftime("%Y-%m-%dT%H:%M:%SZ")
        cls.couch_ids = [
            # field structure based on real auditcare docs in Couch
            save_couch_doc(
                "NavigationEventAudit",
                username,
                event_date=event_date,
                description='User Name',
                extra={},
                headers={
                    'REQUEST_METHOD': 'GET',
                    'QUERY_STRING': 'version=2.0&since=...',
                    'HTTP_CONNECTION': 'close',
                    'HTTP_COOKIE': 'sessionid=abc123',
                    'SERVER_NAME': '0.0.0.0',
                    'SERVER_PORT': '9010',
                    'HTTP_ACCEPT': 'application/json, application/*+json, */*',
                    'REMOTE_ADDR': '10.2.10.60',
                    'HTTP_ACCEPT_ENCODING': 'gzip'
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
                event_date=event_date,
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
                cls.username,
                event_date=event_date,
                description='User Name',
                extra={},
                headers={
                    'REQUEST_METHOD': 'GET',
                    'QUERY_STRING': 'version=2.0&since=...',
                    'HTTP_CONNECTION': 'close',
                    'HTTP_COOKIE': 'sessionid=abc123',
                    'SERVER_NAME': '0.0.0.0',
                    'SERVER_PORT': '9010',
                    'HTTP_ACCEPT': 'application/json, application/*+json, */*',
                    'REMOTE_ADDR': '10.2.10.60',
                    'HTTP_ACCEPT_ENCODING': 'gzip'
                },
                ip_address='10.1.2.3',
                request_path='/a/delmar/phone/restore/?version=2.0&since=...',
                session_key='abc123',
                status_code=200,
                user_agent='okhttp/4.4.1',
                view_kwargs={'domain': 'delmar'},
                view='corehq.apps.ota.views.restore',
            )
        ]

        def iter_events(model, username, **kw):
            for event_date in cls.event_dates:
                yield model(user=username, event_date=event_date, **kw)

        cls.event_dates = [datetime(2021, 2, d, 3) for d in range(1, 29)]
        headers = {"REQUEST_METHOD": "GET"}
        NavigationEventAudit.objects.bulk_create(chain(
            iter_events(NavigationEventAudit, cls.username, headers=headers),
            iter_events(NavigationEventAudit, "other@test.com", headers=headers)
        ))
        AccessAudit.objects.bulk_create(chain(
            iter_events(AccessAudit, cls.username, access_type="o"),
            iter_events(AccessAudit, "other@test.com", access_type="i")
        ))

    @classmethod
    def tearDownClass(cls):
        delete_couch_docs(cls.couch_ids)
        super().tearDownClass()

    def test_navigation_events_query(self):
        events = list(navigation_events_by_user(self.username))
        self.assertEqual({e.user for e in events}, {self.username})
        expected_dates = [datetime(2021, 2, 1, 2, 0)] + self.event_dates
        self.assertEqual([e.event_date for e in events], expected_dates)
        self.assertEqual(len(events), 29)

    def test_navigation_events_date_range_query(self):
        start = datetime(2021, 2, 5)
        end = datetime(2021, 2, 15)
        events = list(navigation_events_by_user(self.username, start, end))
        self.assertEqual({e.user for e in events}, {self.username})
        self.assertEqual({e.event_date for e in events}, set(self.event_dates[4:15]))
        self.assertEqual(len(events), 11)

    @patch('corehq.apps.auditcare.utils.export.get_fixed_start_date_for_sql', return_value=datetime(2021, 2, 3))
    def test_navigation_events_querying_couch_and_sql(self, mock):
        couch_event_date = datetime(2021, 2, 1, 2)
        start = datetime(2021, 1, 31)
        end = datetime(2021, 2, 5)
        events = list(navigation_events_by_user(self.username, start, end))
        self.assertEqual({e.user for e in events}, {self.username})
        expected_event_dates = set(self.event_dates[2:5] + [couch_event_date])
        self.assertEqual({e.event_date for e in events}, expected_event_dates)
        self.assertEqual(len(events), 4)

    def test_recent_all_log_events_query(self):
        start = datetime(2021, 2, 4)
        events = list(get_all_log_events(start))
        self.assertEqual(len(events), 100)
        self.assertEqual({e.user for e in events}, {self.username, "other@test.com"})
        self.assertEqual({e.doc_type for e in events}, {"AccessAudit", "NavigationEventAudit"})
        self.assertEqual({e.event_date for e in events}, set(self.event_dates[3:]))

    def test_all_log_events_date_range_query(self):
        start = datetime(2021, 2, 5)
        end = datetime(2021, 2, 15)
        events = list(get_all_log_events(start, end))
        self.assertEqual({e.user for e in events}, {self.username, "other@test.com"})
        self.assertEqual({e.doc_type for e in events}, {"AccessAudit", "NavigationEventAudit"})
        self.assertEqual({e.event_date for e in events}, set(self.event_dates[4:15]))
        self.assertEqual(len(events), 44)

    def test_all_log_events_query_returns_events_from_couch(self):
        start = datetime(2021, 2, 1)
        end = datetime(2021, 2, 1)
        events = list(get_all_log_events(start, end))
        self.assertEqual({e.user for e in events}, {self.username, "other@test.com", "couch@test.com"})
        self.assertEqual({e.doc_type for e in events}, {"AccessAudit", "NavigationEventAudit"})
        self.assertEqual({e.event_date for e in events}, {datetime(2021, 2, 1, 2), datetime(2021, 2, 1, 3)})
        self.assertEqual(len(events), 7)

    def test_write_export_from_all_log_events(self):
        def unpack(row):
            return {k: row[k] for k in ["Date", "Type", "User", "Description"]}
        start = datetime(2021, 2, 1)
        end = datetime(2021, 2, 1)
        with tempdir() as tmp:
            filename = os.path.join(tmp, "events.csv")
            with open(filename, 'w', encoding="utf-8") as csvfile:
                write_export_from_all_log_events(csvfile, start=start, end=end)
            with open(filename, encoding="utf-8") as fh:
                def key(row):
                    return row["Date"], row["Type"], row["User"]
                rows = DictReader(fh)
                items = sorted([unpack(r) for r in rows], key=key)
                expected_items = [
                    {
                        'Date': '2021-02-01 02:00:00',
                        'Type': 'AccessAudit',
                        'User': 'couch@test.com',
                        'Description': 'Login Success',
                    },
                    {
                        'Date': '2021-02-01 02:00:00',
                        'Type': 'NavigationEventAudit',
                        'User': 'couch@test.com',
                        'Description': 'User Name',
                    },
                    {
                        'Date': '2021-02-01 02:00:00',
                        'Type': 'NavigationEventAudit',
                        'User': 'test@test.com',
                        'Description': 'User Name'
                    },
                    {
                        'Date': '2021-02-01 03:00:00',
                        'Type': 'AccessAudit',
                        'User': 'other@test.com',
                        'Description': 'Login: other@test.com',
                    },
                    {
                        'Date': '2021-02-01 03:00:00',
                        'Type': 'AccessAudit',
                        'User': 'test@test.com',
                        'Description': 'Logout: test@test.com',
                    },
                    {
                        'Date': '2021-02-01 03:00:00',
                        'Type': 'NavigationEventAudit',
                        'User': 'other@test.com',
                        'Description': 'other@test.com',
                    },
                    {
                        'Date': '2021-02-01 03:00:00',
                        'Type': 'NavigationEventAudit',
                        'User': 'test@test.com',
                        'Description': 'test@test.com',
                    },
                ]
                self.assertEqual(items, expected_items)

    def test_query_window_size(self):
        # NOTE small window size ensures multiple queries per event date
        with patch_window_size(1):
            events = list(get_all_log_events(datetime(2021, 2, 4)))
        self.assertEqual(len(events), 100)

    def test_related_query_error(self):
        event = next(iter(navigation_events_by_user('other@test.com')))
        keys = get_foreign_names(NavigationEventAudit)
        self.assertIn("user_agent", keys)
        self.assertIn("user_agent_fk", keys)
        for key in keys:
            with self.assertRaises(ForeignKeyAccessError):
                getattr(event, key)

    def test_get_sql_start_date(self):
        self.assertEqual(get_sql_start_date(), datetime(2021, 2, 1, 3))


@contextmanager
def patch_window_size(size):
    with patch.object(AuditWindowQuery.__init__, "__defaults__", (size,)):
        qry = AuditWindowQuery("ignored")
        assert qry.window_size == size, f"patch failed ({qry.window_size})"
        yield
