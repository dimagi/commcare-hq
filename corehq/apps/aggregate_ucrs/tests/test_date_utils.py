from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from django.test import SimpleTestCase

from corehq.apps.aggregate_ucrs.date_utils import Month


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

    def test_get_previous_month(self):
        month = Month(2018, 3)
        previous = month.get_previous_month()
        self.assertEqual(2018, previous.year)
        self.assertEqual(2, previous.month)

    def test_get_previous_month_year_crossing(self):
        month = Month(2018, 1)
        previous = month.get_previous_month()
        self.assertEqual(2017, previous.year)
        self.assertEqual(12, previous.month)

    def test_get_next_month(self):
        month = Month(2018, 3)
        next = month.get_next_month()
        self.assertEqual(2018, next.year)
        self.assertEqual(4, next.month)

    def test_get_next_month_year_border(self):
        month = Month(2017, 12)
        next = month.get_next_month()
        self.assertEqual(2018, next.year)
        self.assertEqual(1, next.month)
