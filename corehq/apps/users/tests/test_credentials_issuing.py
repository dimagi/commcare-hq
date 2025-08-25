from datetime import datetime, timezone, date
from dateutil.relativedelta import relativedelta

from django.test import SimpleTestCase

from corehq.apps.users.credentials_issuing import has_consecutive_months


class TestHasConsecutiveMonths(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.three_months = [
            datetime.now(timezone.utc) - relativedelta(months=1),
            datetime.now(timezone.utc) - relativedelta(months=3),
            datetime.now(timezone.utc) - relativedelta(months=7),
            datetime.now(timezone.utc) - relativedelta(months=4),
            datetime.now(timezone.utc) - relativedelta(months=5),
        ]

        self.two_months_across_years = [
            date(year=2023, month=12, day=1),
            date(year=2024, month=3, day=1),
            date(year=2024, month=1, day=1),
        ]

    def test_has_consecutive_months(self):
        assert has_consecutive_months(self.three_months, required_months=3) is True
        assert has_consecutive_months(self.three_months, required_months=2) is True

    def test_consecutive_month_across_years(self):
        assert has_consecutive_months(self.two_months_across_years, required_months=2) is True

    def test_no_consecutive_months(self):
        assert has_consecutive_months(self.three_months, required_months=4) is False
