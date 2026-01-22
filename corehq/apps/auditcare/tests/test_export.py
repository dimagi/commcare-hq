import os.path
import uuid
from contextlib import contextmanager
from csv import DictReader
from datetime import datetime, timedelta
from itertools import chain
from unittest.mock import patch

from testil import tempdir

from corehq.apps.auditcare.models import AccessAudit, NavigationEventAudit

from ..utils.export import (
    AuditWindowQuery,
    ForeignKeyAccessError,
    get_all_log_events,
    get_date_range_where,
    get_domain_first_access_times,
    get_foreign_names,
    navigation_events_by_user,
    write_export_from_all_log_events,
)
from .testutils import AuditcareTest


class TestNavigationEventsQueries(AuditcareTest):

    maxDiff = None
    username = "test@test.com"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

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
        super().tearDownClass()

    def test_navigation_events_query(self):
        events = list(navigation_events_by_user(self.username))
        self.assertEqual({e.user for e in events}, {self.username})
        expected_dates = self.event_dates
        self.assertEqual([e.event_date for e in events], expected_dates)
        self.assertEqual(len(events), 28)

    def test_navigation_events_date_range_query(self):
        start = datetime(2021, 2, 5)
        end = datetime(2021, 2, 15)
        events = list(navigation_events_by_user(self.username, start_date=start, end_date=end))
        self.assertEqual({e.user for e in events}, {self.username})
        self.assertEqual({e.event_date for e in events}, set(self.event_dates[4:15]))
        self.assertEqual(len(events), 11)

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
        self.assertEqual({e.user for e in events}, {self.username, "other@test.com"})
        self.assertEqual({e.doc_type for e in events}, {"AccessAudit", "NavigationEventAudit"})
        self.assertEqual({e.event_date for e in events}, {datetime(2021, 2, 1, 3)})
        self.assertEqual(len(events), 4)

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

    def test_get_domain_first_access_times(self):

        def create_session_events(domain):
            login_event = dict(
                user=self.username,
                domain=domain,
                session_key=uuid.uuid4().hex,
                event_date=datetime.utcnow(),
            )
            for event_domain, minutes in [(None, -1),
                                          (domain, 0),
                                          (domain, 1)]:
                fields = login_event.copy()
                # save one event with domain/date changed by loop params:
                fields["domain"] = event_domain
                fields['event_date'] += timedelta(minutes=minutes)
                NavigationEventAudit(**fields).save()
                # update the fields and save another:
                #   - same session
                #   - different domain
                #   - 5 minutes ealier
                fields["domain"] = "not-queried"
                fields["event_date"] += timedelta(minutes=-5)
                NavigationEventAudit(**fields).save()
            return login_event

        domain = "delmar"
        login_events = []
        for x in range(2):
            login_event = create_session_events(domain)
            # rename `event_date` to `access_time` (name of aggregation field)
            login_event["access_time"] = login_event.pop("event_date")
            login_events.append(login_event)
            # remove the session key (not returned by the query)
            del login_event["session_key"]
        self.assertEqual(list(get_domain_first_access_times([domain])), login_events)


class TestNavigationEventsQueriesWithoutData(AuditcareTest):

    def test_get_all_log_events_returns_empty(self):
        start = end = datetime.utcnow()
        self.assertEqual(list(get_all_log_events(start, end)), [])


@contextmanager
def patch_window_size(size):
    with patch.object(AuditWindowQuery.__init__, "__defaults__", (size,)):
        qry = AuditWindowQuery("ignored")
        assert qry.window_size == size, f"patch failed ({qry.window_size})"
        yield


class TestGetDateRangeWhere(AuditcareTest):
    """Test get_date_range_where with various date/datetime inputs."""

    def test_with_datetime_objects(self):
        start = datetime(2021, 2, 5, 9, 30)
        end = datetime(2021, 2, 15, 17, 45)
        where = get_date_range_where(start, end)
        self.assertEqual(where["event_date__gt"], datetime(2021, 2, 5, 9, 30))
        self.assertEqual(where["event_date__lt"], datetime(2021, 2, 15, 17, 45))

    def test_with_date_objects(self):
        from datetime import date
        start = date(2021, 2, 5)
        end = date(2021, 2, 15)
        where = get_date_range_where(start, end)
        # Date objects should be converted to datetime at start of day
        self.assertEqual(where["event_date__gt"], datetime(2021, 2, 5, 0, 0))
        # End date should be inclusive (add 1 day for lt)
        self.assertEqual(where["event_date__lt"], datetime(2021, 2, 16, 0, 0))

    def test_with_string_dates(self):
        start = "2021-02-05"
        end = "2021-02-15"
        where = get_date_range_where(start, end)
        self.assertEqual(where["event_date__gt"], datetime(2021, 2, 5, 0, 0))
        # String dates should have 1 day added for inclusive behavior
        self.assertEqual(where["event_date__lt"], datetime(2021, 2, 16, 0, 0))

    def test_with_none_start(self):
        end = datetime(2021, 2, 15, 17, 45)
        where = get_date_range_where(None, end)
        self.assertNotIn("event_date__gt", where)
        self.assertEqual(where["event_date__lt"], datetime(2021, 2, 15, 17, 45))

    def test_with_none_end(self):
        start = datetime(2021, 2, 5, 9, 30)
        where = get_date_range_where(start, None)
        self.assertEqual(where["event_date__gt"], datetime(2021, 2, 5, 9, 30))
        self.assertNotIn("event_date__lt", where)

    def test_with_both_none(self):
        where = get_date_range_where(None, None)
        self.assertEqual(where, {})

    def test_with_midnight_datetime_as_end(self):
        """Datetime at midnight should be treated as a date (inclusive of full day)."""
        start = datetime(2021, 2, 5)  # midnight
        end = datetime(2021, 2, 15)  # midnight
        where = get_date_range_where(start, end)
        # End at midnight should add 1 day to include the full day
        self.assertEqual(where["event_date__gt"], datetime(2021, 2, 5, 0, 0))
        self.assertEqual(where["event_date__lt"], datetime(2021, 2, 16, 0, 0))

