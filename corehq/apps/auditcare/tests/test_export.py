from contextlib import contextmanager
from datetime import datetime
from itertools import chain
from unittest.mock import patch

from corehq.apps.auditcare.models import AccessAudit, NavigationEventAudit

from ..utils.export import (
    AuditWindowQuery,
    ForeignKeyAccessError,
    get_all_log_events,
    get_foreign_names,
    navigation_events_by_user,
)
from .testutils import AuditcareTest


class TestNavigationEventsQueries(AuditcareTest):

    username = "test@test.com"

    @classmethod
    def setUpTestData(cls):
        def iter_events(model, username):
            for event_date in cls.event_dates:
                yield model(user=username, event_date=event_date)

        cls.event_dates = [datetime(2021, 2, d, 3) for d in range(1, 29)]
        NavigationEventAudit.objects.bulk_create(chain(
            iter_events(NavigationEventAudit, cls.username),
            iter_events(NavigationEventAudit, "other@test.com")
        ))
        AccessAudit.objects.bulk_create(chain(
            iter_events(AccessAudit, cls.username),
            iter_events(AccessAudit, "other@test.com")
        ))

    def test_navigation_events_query(self):
        events = navigation_events_by_user(self.username)
        self.assertEqual(events.count(), 28)
        self.assertEqual({e.user for e in events}, {self.username})
        self.assertEqual([e.event_date for e in events], self.event_dates)

    def test_navigation_events_date_range_query(self):
        start = datetime(2021, 2, 5)
        end = datetime(2021, 2, 15)
        events = navigation_events_by_user(self.username, start, end)
        self.assertEqual(events.count(), 11)
        events = list(events)
        self.assertEqual({e.user for e in events}, {self.username})
        self.assertEqual({e.event_date for e in events}, set(self.event_dates[4:15]))

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

    def test_query_window_size(self):
        # NOTE small window size ensures multiple queries per event date
        with patch_window_size(1):
            events = list(get_all_log_events(datetime(2021, 2, 4)))
        self.assertEqual(len(events), 100)

    def test_related_query_error(self):
        event = next(iter(navigation_events_by_user(self.username)))
        keys = get_foreign_names(NavigationEventAudit)
        self.assertIn("user_agent", keys)
        self.assertIn("user_agent_fk", keys)
        for key in keys:
            with self.assertRaises(ForeignKeyAccessError):
                getattr(event, key)


@contextmanager
def patch_window_size(size):
    with patch.object(AuditWindowQuery.__init__, "__defaults__", (size,)):
        qry = AuditWindowQuery("ignored", {})
        assert qry.window_size == size, f"patch failed ({qry.window_size})"
        yield
