from datetime import date, datetime
from unittest.mock import MagicMock, patch

from dimagi.utils.dates import DateSpan
from django.test import RequestFactory, TestCase

from corehq.apps.auditcare.models import AccessAudit, NavigationEventAudit
from corehq.apps.auditcare.tests.testutils import AuditcareTest
from corehq.apps.hqadmin.reports import (
    UserAuditReport,
    truncate_rows_to_minute_boundary,
)
from corehq.apps.reports.filters.simple import IPAddressFilter, StatusCodeFilter


class TestIPAddressParsing(TestCase):

    def test_single_ip(self):
        result = IPAddressFilter.parse_ip_input("192.168.1.1")
        self.assertEqual(result, [("exact", "192.168.1.1")])

    def test_cidr_32(self):
        result = IPAddressFilter.parse_ip_input("192.168.1.1/32")
        self.assertEqual(result, [("exact", "192.168.1.1")])

    def test_cidr_24(self):
        result = IPAddressFilter.parse_ip_input("192.168.1.0/24")
        self.assertEqual(result, [("startswith", "192.168.1.")])

    def test_cidr_16(self):
        result = IPAddressFilter.parse_ip_input("172.16.0.0/16")
        self.assertEqual(result, [("startswith", "172.16.")])

    def test_cidr_8(self):
        result = IPAddressFilter.parse_ip_input("10.0.0.0/8")
        self.assertEqual(result, [("startswith", "10.")])

    def test_comma_separated(self):
        result = IPAddressFilter.parse_ip_input("10.0.0.0/8, 192.168.1.0/24")
        self.assertEqual(result, [
            ("startswith", "10."),
            ("startswith", "192.168.1."),
        ])

    def test_invalid_cidr_suffix(self):
        result = IPAddressFilter.parse_ip_input("10.0.0.0/12")
        self.assertEqual(result, None)

    def test_empty_input(self):
        result = IPAddressFilter.parse_ip_input("")
        self.assertEqual(result, [])

    def test_whitespace_only(self):
        result = IPAddressFilter.parse_ip_input("   ")
        self.assertEqual(result, [])


class TestStatusCodeParsing(TestCase):

    def test_single_code(self):
        self.assertEqual(StatusCodeFilter.parse_status_codes("200"), [200])

    def test_multiple_codes(self):
        self.assertEqual(StatusCodeFilter.parse_status_codes("200, 403, 500"), [200, 403, 500])

    def test_empty_input(self):
        self.assertEqual(StatusCodeFilter.parse_status_codes(""), [])

    def test_whitespace_only(self):
        self.assertEqual(StatusCodeFilter.parse_status_codes("   "), [])

    def test_invalid_input(self):
        self.assertIsNone(StatusCodeFilter.parse_status_codes("200, abc"))

    def test_trailing_comma(self):
        self.assertEqual(StatusCodeFilter.parse_status_codes("200, 403,"), [200, 403])


class TestTruncateRowsToMinuteBoundary(TestCase):

    def _make_row(self, event_date):
        """Create a minimal row list matching the report format.
        Index 0 is the formatted date string."""
        return [event_date.strftime("%Y-%m-%d %H:%M:%S.%f UTC")] + [""] * 8

    def test_no_truncation_under_limit(self):
        rows = [self._make_row(datetime(2026, 3, 27, 15, m)) for m in range(10)]
        result, cutoff_dt = truncate_rows_to_minute_boundary(rows, max_records=5000)
        self.assertEqual(len(result), 10)
        self.assertIsNone(cutoff_dt)

    def test_truncation_at_minute_boundary(self):
        # 3 rows at 15:00, 3 rows at 15:01, 3 rows at 15:02 = 9 rows
        rows = []
        for minute in [0, 1, 2]:
            for second in [10, 20, 30]:
                rows.append(self._make_row(datetime(2026, 3, 27, 15, minute, second)))
        result, cutoff_dt = truncate_rows_to_minute_boundary(rows, max_records=8)
        # Should truncate to rows with event_date < 15:02:00, which gives us 6 rows (15:00 and 15:01)
        self.assertEqual(len(result), 6)
        self.assertEqual(cutoff_dt, datetime(2026, 3, 27, 15, 2))

    def test_truncation_same_minute_edge_case(self):
        # All rows in the same minute
        rows = [self._make_row(datetime(2026, 3, 27, 15, 0, s)) for s in range(10)]
        result, cutoff_dt = truncate_rows_to_minute_boundary(rows, max_records=8)
        # Can't trim meaningfully — return first max_records rows
        self.assertEqual(len(result), 8)
        self.assertIsNone(cutoff_dt)  # None signals same-minute edge case

    def test_truncation_preserves_sort_order(self):
        rows = []
        for minute in [0, 1, 2, 3]:
            rows.append(self._make_row(datetime(2026, 3, 27, 15, minute, 30)))
        result, cutoff_dt = truncate_rows_to_minute_boundary(rows, max_records=3)
        # Truncate to < 15:03:00, giving us rows at 15:00, 15:01, 15:02
        self.assertEqual(len(result), 3)
        self.assertEqual(cutoff_dt, datetime(2026, 3, 27, 15, 3))

    def test_truncation_large_cluster_at_boundary(self):
        # 2 rows at 15:00, 5 rows at 15:01 = 7 total, limit=6
        rows = []
        for s in [10, 20]:
            rows.append(self._make_row(datetime(2026, 3, 27, 15, 0, s)))
        for s in [10, 20, 30, 40, 50]:
            rows.append(self._make_row(datetime(2026, 3, 27, 15, 1, s)))
        result, cutoff_dt = truncate_rows_to_minute_boundary(rows, max_records=6)
        # Can only keep rows < 15:01:00, which is the 2 rows at 15:00
        self.assertEqual(len(result), 2)
        self.assertEqual(cutoff_dt, datetime(2026, 3, 27, 15, 1))


def _make_mock_couch_user():
    mock_user = MagicMock()
    mock_user._id = 'test-user-id'
    mock_user.can_view_some_reports.return_value = True
    return mock_user


class TestUserAuditReportFilters(AuditcareTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        headers = {"REQUEST_METHOD": "GET"}
        NavigationEventAudit.objects.bulk_create([
            NavigationEventAudit(
                user="admin@test.com",
                domain="test-domain",
                event_date=datetime(2026, 3, 27, 15, 0, i),
                ip_address="10.0.0.1",
                path="/a/test-domain/dashboard/",
                headers=headers,
                status_code=200,
            )
            for i in range(5)
        ] + [
            NavigationEventAudit(
                user="admin@test.com",
                domain="test-domain",
                event_date=datetime(2026, 3, 27, 15, 0, 10),
                ip_address="192.168.1.100",
                path="/a/test-domain/api/v1/cases/",
                headers=headers,
                status_code=404,
            ),
        ])
        AccessAudit.objects.create(
            user="admin@test.com",
            domain="test-domain",
            event_date=datetime(2026, 3, 27, 15, 0, 5),
            ip_address="10.0.0.1",
            path="/a/test-domain/login/",
            access_type="i",
        )

    def _get_report(self, params):
        request = self.factory.get('/hq/admin/user_audit_report/', params)
        request.couch_user = _make_mock_couch_user()
        request.can_access_all_locations = True
        # Set up request.datespan from the startdate/enddate params so DatespanMixin
        # picks up the correct date range.
        startdate = date.fromisoformat(params['startdate'])
        enddate = date.fromisoformat(params['enddate'])
        request.datespan = DateSpan(startdate, enddate)
        report = UserAuditReport(request, domain=None)
        return report

    def test_ip_filter_exact(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'ip_address': '192.168.1.100',
        })
        rows = report.rows
        self.assertEqual(len(rows), 1)
        self.assertIn('192.168.1.100', rows[0][4])

    def test_ip_filter_cidr(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'ip_address': '10.0.0.0/8',
        })
        rows = report.rows
        self.assertEqual(len(rows), 6)  # 5 nav events + 1 access event

    def test_status_code_filter(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'status_code': '404',
        })
        rows = report.rows
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][7], 404)

    def test_url_include_contains(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'url_include': '/api/',
            'url_include_mode': 'contains',
        })
        rows = report.rows
        self.assertEqual(len(rows), 1)

    def test_url_exclude_contains(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'url_exclude': '/dashboard/',
            'url_exclude_mode': 'contains',
        })
        rows = report.rows
        # API row + AccessAudit login row (neither contains /dashboard/)
        nav_rows = [r for r in rows if r[1] == 'NavigationEventAudit']
        self.assertEqual(len(nav_rows), 1)

    def test_url_include_mode_defaults_for_invalid_input(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'url_include_mode': 'iregex',
        })
        self.assertEqual(report.selected_url_include_mode, 'contains')

    def test_url_exclude_mode_defaults_for_invalid_input(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'url_exclude_mode': 'regex',
        })
        self.assertEqual(report.selected_url_exclude_mode, 'contains')

    def test_status_code_filter_excludes_access_events(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'status_code': '200',
        })
        rows = report.rows
        for row in rows:
            self.assertEqual(row[1], 'NavigationEventAudit')

    def test_no_status_code_filter_includes_access_events(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
        })
        rows = report.rows
        doc_types = {row[1] for row in rows}
        self.assertIn('AccessAudit', doc_types)
        self.assertIn('NavigationEventAudit', doc_types)

    def test_url_include_and_exclude_combined(self):
        """Include URLs containing /a/test-domain/ but exclude /dashboard/"""
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'url_include': '/a/test-domain/',
            'url_include_mode': 'contains',
            'url_exclude': '/dashboard/',
            'url_exclude_mode': 'contains',
        })
        rows = report.rows
        # Should get the API row and the AccessAudit login row
        nav_rows = [r for r in rows if r[1] == 'NavigationEventAudit']
        self.assertEqual(len(nav_rows), 1)
        self.assertIn('/api/', nav_rows[0][6])

    def test_url_include_startswith(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'url_include': '/a/test-domain/api/',
            'url_include_mode': 'startswith',
        })
        rows = report.rows
        nav_rows = [r for r in rows if r[1] == 'NavigationEventAudit']
        self.assertEqual(len(nav_rows), 1)

    def test_no_user_no_domain_returns_empty(self):
        report = self._get_report({
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
        })
        rows = report.rows
        self.assertEqual(rows, [])

    def test_events_interleave_by_date(self):
        """Nav and access events should be merged in chronological order."""
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
        })
        rows = report.rows
        # Verify rows are sorted by date
        dates = [row[0] for row in rows]
        self.assertEqual(dates, sorted(dates))
        # Verify both types are present (not all of one then all of other)
        doc_types = [row[1] for row in rows]
        self.assertIn('AccessAudit', doc_types)
        self.assertIn('NavigationEventAudit', doc_types)


class TestUserAuditReportTruncation(AuditcareTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        headers = {"REQUEST_METHOD": "GET"}
        events = []
        for minute in range(3):
            for second in range(10):
                events.append(NavigationEventAudit(
                    user="bulk@test.com",
                    domain="test-domain",
                    event_date=datetime(2026, 3, 27, 15, minute, second),
                    ip_address="10.0.0.1",
                    path="/a/test-domain/dashboard/",
                    headers=headers,
                    status_code=200,
                ))
        NavigationEventAudit.objects.bulk_create(events)

    def _get_report(self, params):
        request = RequestFactory().get('/hq/admin/user_audit_report/', params)
        request.couch_user = _make_mock_couch_user()
        request.can_access_all_locations = True
        startdate = date.fromisoformat(params['startdate'])
        enddate = date.fromisoformat(params['enddate'])
        request.datespan = DateSpan(startdate, enddate)
        return UserAuditReport(request, domain=None)

    def test_truncation_sets_context(self):
        report = self._get_report({
            'username': 'bulk@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
        })
        with patch.object(UserAuditReport, 'MAX_RECORDS', 15):
            rows = report.rows
            self.assertLessEqual(len(rows), 15)
            self.assertTrue(
                report._truncation_cutoff is not None
                or report._truncation_same_minute
            )

    def test_truncation_result_matches_narrower_query(self):
        """The truncated result should match what you'd get with the narrower time range."""
        report = self._get_report({
            'username': 'bulk@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
        })
        with patch.object(UserAuditReport, 'MAX_RECORDS', 15):
            rows = report.rows
            cutoff = report._truncation_cutoff

        if cutoff is not None:
            # Now query with the narrower time range that truncation would suggest
            narrower_report = self._get_report({
                'username': 'bulk@test.com',
                'startdate': '2026-03-27',
                'enddate': cutoff.strftime('%Y-%m-%d'),
                'end_time': cutoff.strftime('%H:%M'),
            })
            # Need high limit so no truncation happens on the narrower query
            with patch.object(UserAuditReport, 'MAX_RECORDS', 50000):
                narrower_rows = narrower_report.rows
            self.assertEqual(len(rows), len(narrower_rows))
