import datetime
from decimal import Decimal

from corehq.apps.project_db.coerce import coerce_to_date, coerce_to_number


class TestCoerceToDate:

    def test_iso_date(self):
        assert coerce_to_date('2024-03-15') == datetime.date(2024, 3, 15)

    def test_iso_datetime(self):
        assert coerce_to_date('2024-03-15T10:30:00') == datetime.date(2024, 3, 15)

    def test_none(self):
        assert coerce_to_date(None) is None

    def test_empty_string(self):
        assert coerce_to_date('') is None

    def test_invalid_string(self):
        assert coerce_to_date('not-a-date') is None

    def test_partial_date(self):
        assert coerce_to_date('2024-13-01') is None


class TestCoerceToNumber:

    def test_integer_string(self):
        assert coerce_to_number('42') == Decimal('42')

    def test_decimal_string(self):
        assert coerce_to_number('3.14') == Decimal('3.14')

    def test_negative(self):
        assert coerce_to_number('-7.5') == Decimal('-7.5')

    def test_none(self):
        assert coerce_to_number(None) is None

    def test_empty_string(self):
        assert coerce_to_number('') is None

    def test_invalid_string(self):
        assert coerce_to_number('abc') is None

    def test_whitespace(self):
        assert coerce_to_number('  ') is None
