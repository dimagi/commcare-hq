from datetime import date

from django.test import SimpleTestCase

from corehq.apps.accounting.utils import is_date_range_overlapping


class TestIsDateRangeOverlapping(SimpleTestCase):
    def test_first_range_is_contained_in_second_range(self):
        assert is_date_range_overlapping(date(2025, 1, 3), date(2025, 1, 6),
                                         date(2025, 1, 1), date(2025, 1, 10))

    def test_second_range_is_contained_in_first_range(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2025, 1, 5), date(2025, 1, 7))

    def test_partial_overlap_start(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2024, 12, 20), date(2025, 1, 2))

    def test_partial_overlap_end(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2025, 1, 9), date(2025, 1, 20))

    def test_exact_overlap(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2025, 1, 1), date(2025, 1, 10))

    def test_no_overlap_before(self):
        assert not is_date_range_overlapping(date(2025, 1, 10), date(2025, 1, 20),
                                             date(2025, 1, 1), date(2025, 1, 9))

    def test_no_overlap_after(self):
        assert not is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 9),
                                             date(2025, 1, 10), date(2025, 1, 20))

    def test_adjacent_ranges_do_not_overlap(self):
        # Two ranges that touch at a boundary is not considered an overlap.
        # This is a special case for our accounting system
        assert not is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                             date(2025, 1, 10), date(2025, 1, 20))

        assert not is_date_range_overlapping(date(2025, 1, 10), date(2025, 1, 20),
                                             date(2025, 1, 1), date(2025, 1, 10))

    def test_same_start_date_is_overlap(self):
        assert is_date_range_overlapping(date(2025, 1, 5), date(2025, 1, 10),
                                         date(2025, 1, 5), date(2025, 1, 15))

    def test_same_end_date_is_overlap(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2025, 1, 5), date(2025, 1, 10))

    def test_first_range_infinite_end(self):
        assert is_date_range_overlapping(date(2025, 1, 1), None,
                                         date(2025, 1, 10), date(2025, 1, 20))

    def test_second_range_infinite_end(self):
        assert is_date_range_overlapping(date(2025, 1, 10), date(2025, 1, 20),
                                         date(2025, 1, 1), None)

    def test_both_ranges_infinite_end(self):
        assert is_date_range_overlapping(date(2025, 1, 1), None,
                                         date(2025, 2, 1), None)

    def test_first_range_infinite_end_but_start_after_second_range_end(self):
        assert not is_date_range_overlapping(date(2025, 1, 1), None,
                                             date(2024, 1, 1), date(2024, 12, 31))

    def test_second_range_infinite_end_but_start_after_first_range_end(self):
        assert not is_date_range_overlapping(date(2024, 1, 1), date(2024, 12, 31),
                                             date(2025, 1, 1), None)
