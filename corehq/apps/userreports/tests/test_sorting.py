import datetime
from django.test import SimpleTestCase
from corehq.apps.userreports.reports.sorting import get_default_sort_value, ASCENDING, DESCENDING


class SortingTestCase(SimpleTestCase):

    def test_date_default(self):
        self.assertTrue(get_default_sort_value('date') < datetime.datetime.now().date())

    def test_datetime_default(self):
        self.assertTrue(get_default_sort_value('datetime') < datetime.datetime.now())

    def test_string_default(self):
        self.assertEqual('', get_default_sort_value('string'))

    def test_other_defaults(self):
        self.assertEqual(None, get_default_sort_value('missing_type'))
