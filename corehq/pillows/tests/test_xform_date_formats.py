import pytest

from corehq.pillows.xform import is_valid_date, normalize_date_for_es


class TestIsValidDate:

    @pytest.mark.parametrize("date_str,expected", [
        ("2025-01-13T16:05:01Z", True),
        ("2025-01-13T16:05:01.123Z", True),
        ("2025-01-13T16:05:01.123456Z", True),
        ("2025-01-13T16:05:01.1234567Z", True),  # 7 digits, valid in Python
        ("2025-01-13", True),
        ("invalid-date", False),
        ("", False),
        (None, False),
    ])
    def test_is_valid_date(self, date_str, expected):
        assert is_valid_date(date_str) == expected


class TestNormalizeDateForEs:

    @pytest.mark.parametrize("input_date,expected", [
        # Dates with 7+ fractional digits should be truncated to 6
        ("2026-01-19T07:23:45.1498543Z", "2026-01-19T07:23:45.149854Z"),
        ("2025-01-13T16:05:01.0294562Z", "2025-01-13T16:05:01.029456Z"),
        ("2025-01-13T16:05:01.1234567890Z", "2025-01-13T16:05:01.123456Z"),
        # Dates with 6 or fewer fractional digits should pass through unchanged
        ("2025-01-13T16:05:01.123456Z", "2025-01-13T16:05:01.123456Z"),
        ("2025-01-13T16:05:01.123Z", "2025-01-13T16:05:01.123Z"),
        ("2025-01-13T16:05:01Z", "2025-01-13T16:05:01Z"),
        ("2025-01-13", "2025-01-13"),
        # Dates with timezone offsets
        ("2025-01-13T16:05:01.1234567+05:30", "2025-01-13T16:05:01.123456+05:30"),
        ("2025-01-13T16:05:01.1234567-08:00", "2025-01-13T16:05:01.123456-08:00"),
        # Edge cases
        (None, None),
        ("", ""),
        # Dates with space separator instead of T
        ("2025-01-13 16:05:01.1234567Z", "2025-01-13 16:05:01.123456Z"),
    ])
    def test_normalize_date_for_es(self, input_date, expected):
        assert normalize_date_for_es(input_date) == expected
