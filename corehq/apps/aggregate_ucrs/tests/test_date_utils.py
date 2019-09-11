from datetime import datetime

from django.test import SimpleTestCase

from corehq.apps.aggregate_ucrs.date_utils import Month, Week


class MonthTest(SimpleTestCase):

    def test_start(self):
        month = Month(2018, 3)
        self.assertEqual(datetime(2018, 3, 1), month.start)

    def test_end(self):
        month = Month(2018, 3)
        self.assertEqual(datetime(2018, 4, 1), month.end)

    def test_end_year_crossing(self):
        month = Month(2017, 12)
        self.assertEqual(datetime(2018, 1, 1), month.end)

    def test_get_previous_period(self):
        month = Month(2018, 3)
        previous = month.get_previous_period()
        self.assertEqual(2018, previous.year)
        self.assertEqual(2, previous.month)

    def test_get_previous_period_year_crossing(self):
        month = Month(2018, 1)
        previous = month.get_previous_period()
        self.assertEqual(2017, previous.year)
        self.assertEqual(12, previous.month)

    def test_get_next_period(self):
        month = Month(2018, 3)
        next = month.get_next_period()
        self.assertEqual(2018, next.year)
        self.assertEqual(4, next.month)

    def test_get_next_period_year_border(self):
        month = Month(2017, 12)
        next = month.get_next_period()
        self.assertEqual(2018, next.year)
        self.assertEqual(1, next.month)


class WeekTest(SimpleTestCase):

    def test_start(self):
        self.assertEqual(datetime(2014, 12, 29), Week(2015, 1).start)
        self.assertEqual(datetime(2016, 1, 4), Week(2016, 1).start)
        self.assertEqual(datetime(2017, 1, 2), Week(2017, 1).start)
        self.assertEqual(datetime(2018, 1, 1), Week(2018, 1).start)
        self.assertEqual(datetime(2018, 5, 21), Week(2018, 21).start)

    def test_end(self):
        self.assertEqual(datetime(2015, 1, 5), Week(2015, 1).end)
        self.assertEqual(datetime(2016, 1, 11), Week(2016, 1).end)
        self.assertEqual(datetime(2017, 1, 9), Week(2017, 1).end)
        self.assertEqual(datetime(2018, 1, 8), Week(2018, 1).end)
        self.assertEqual(datetime(2018, 5, 28), Week(2018, 21).end)

    def test_end_year_crossing(self):
        week = Week(2017, 52)
        self.assertEqual(datetime(2018, 1, 1), week.end)

    def test_get_previous_period(self):
        week = Week(2018, 3)
        previous = week.get_previous_period()
        self.assertEqual(2018, previous.year)
        self.assertEqual(2, previous.week)

    def test_get_previous_period_year_crossing(self):
        week = Week(2018, 1)
        previous = week.get_previous_period()
        self.assertEqual(2017, previous.year)
        self.assertEqual(52, previous.week)

    def test_get_next_period(self):
        week = Week(2018, 3)
        next = week.get_next_period()
        self.assertEqual(2018, next.year)
        self.assertEqual(4, next.week)

    def test_get_next_period_year_border(self):
        week = Week(2017, 52)
        next = week.get_next_period()
        self.assertEqual(2018, next.year)
        self.assertEqual(1, next.week)
