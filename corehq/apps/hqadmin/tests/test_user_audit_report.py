from datetime import datetime

from django.test import TestCase

from corehq.apps.hqadmin.reports import truncate_rows_to_minute_boundary
from corehq.apps.reports.filters.simple import IPAddressFilter


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
