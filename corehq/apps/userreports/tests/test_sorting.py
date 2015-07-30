import datetime
from django.test import SimpleTestCase
from corehq.apps.userreports.reports.sorting import get_default_sort_value, ASCENDING, DESCENDING


class SortingTestCase(SimpleTestCase):

    def test_date_defaults(self):
        self.assertTrue(get_default_sort_value('date', ASCENDING) > datetime.datetime.now().date())
        self.assertTrue(get_default_sort_value('date', DESCENDING) < datetime.datetime.now().date())

    def test_datetime_defaults(self):
        self.assertTrue(get_default_sort_value('datetime', ASCENDING) > datetime.datetime.now())
        self.assertTrue(get_default_sort_value('datetime', DESCENDING) < datetime.datetime.now())

    def test_other_defaults(self):
        self.assertEqual(None, get_default_sort_value('missing_type', ASCENDING))
        self.assertEqual(None, get_default_sort_value('missing_type', DESCENDING))
