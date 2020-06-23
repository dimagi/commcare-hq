from datetime import date, datetime, time

from django.test import SimpleTestCase

from corehq.util.workbook_reading.adapters.utils import format_str_to_its_type


class FormatStrToItsTypeTest(SimpleTestCase):
    def test_empty_str(self):
        """Passing an empty string returns None."""
        self.assertEqual(format_str_to_its_type(""), None)

    def test_integer(self):
        """Passing an integer string returns the integer."""
        self.assertEqual(format_str_to_its_type("1"), 1)
        self.assertEqual(format_str_to_its_type("123456789"), 123456789)
        self.assertEqual(format_str_to_its_type("-1"), -1)

    def test_float(self):
        """Passing a float string returns the float."""
        self.assertEqual(format_str_to_its_type("1.23"), 1.23)
        self.assertEqual(format_str_to_its_type("1234.56789"), 1234.56789)
        self.assertEqual(format_str_to_its_type("-9.87"), -9.87)

    def test_datetime(self):
        """Passing a datetime string returns the datetime."""
        subtests = (
            # str_value,         expected_datetime
            ("2000-01-01 00:00", datetime(year=2000, month=1, day=1, hour=0, minute=0)),
            ("12/31/1999 12:34", datetime(year=1999, month=12, day=31, hour=12, minute=34)),
            ("1/1/2001 8:15", datetime(year=2001, month=1, day=1, hour=8, minute=15)),
            ("04.01.2001 23:59", datetime(year=2001, month=4, day=1, hour=23, minute=59)),
            ("30 12 2000 1:02", datetime(year=2000, month=12, day=30, hour=1, minute=2)),
        )
        for (str_value, expected_datetime) in subtests:
            with self.subTest(str_value=str_value, expected_datetime=expected_datetime):
                self.assertEqual(format_str_to_its_type(str_value), expected_datetime)

    def test_date(self):
        """Passing a date string returns the date."""
        subtests = (
            # str_value,         expected_date
            ("2000-01-01", date(year=2000, month=1, day=1,)),
            ("12/31/1999", date(year=1999, month=12, day=31)),
            ("1/1/2001", date(year=2001, month=1, day=1)),
            ("04.01.2001", date(year=2001, month=4, day=1)),
            ("30 12 2000", date(year=2000, month=12, day=30)),
        )
        for (str_value, expected_date) in subtests:
            with self.subTest(str_value=str_value, expected_date=expected_date):
                self.assertEqual(format_str_to_its_type(str_value), expected_date)

    def test_time(self):
        """Passing a time string returns the time."""
        subtests = (
            # str_value,         expected_datetime
            ("00:00:00", time(hour=0, minute=0, second=0)),
            ("12:34:56", time(hour=12, minute=34, second=56)),
            ("8:15", time(hour=8, minute=15)),
            ("23:59", time(hour=23, minute=59)),
            ("1:02", time(hour=1, minute=2)),
        )
        for (str_value, expected_datetime) in subtests:
            with self.subTest(str_value=str_value, expected_datetime=expected_datetime):
                self.assertEqual(format_str_to_its_type(str_value), expected_datetime)

    def test_boolean(self):
        """Passing a boolean string returns the boolean."""
        true_values = [
            "True", " TRUE", "TrUe ", "  TRUE  ", "true", "T", "t", "Yes", "YES",
            "yes", "yEs", "Y", "y", "1"
        ]
        for value in true_values:
            with self.subTest(value=value):
                self.assertEqual(format_str_to_its_type(value), True)

        false_values = [
            "False", " FALSE", "FaLsE ", "  FALSE  ", "false", "F", "f", "No", "NO",
            "no", "nO", "N", "n", "0"
        ]
        for value in false_values:
            with self.subTest(value=value):
                self.assertEqual(format_str_to_its_type(value), False)

    def test_percent(self):
        """Passing a percent string returns the percent."""
        self.assertEqual(format_str_to_its_type("12%"), 0.12)
        self.assertEqual(format_str_to_its_type("99.99%"), 0.9999)
        self.assertEqual(format_str_to_its_type("2%"), 0.02)

    def test_non_strings(self):
        """Passing non-strings to format_str_to_its_type() raises errors."""
        for value in [None, 1, 2.3, True, 1 / 2]:
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    format_str_to_its_type(value)

    def test_non_matching_strings(self):
        """Passing strings that don't match a type returns the non-matching string.."""
        for value in [
            "a", " ", "word", "A phrase with words. Another sentence here.", "$",
            "['list', 'with', 'items']", "{'dictionary': 'with items'}"
        ]:
            with self.subTest(value=value):
                self.assertEqual(format_str_to_its_type(value), value)
