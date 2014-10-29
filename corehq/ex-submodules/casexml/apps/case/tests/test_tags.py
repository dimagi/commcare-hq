from django.test import SimpleTestCase
from casexml.apps.case.templatetags.case_tags import normalize_date
from datetime import date, datetime


class TestCaseTags(SimpleTestCase):

    def test_normalize_date(self):
        self.assertIsInstance(normalize_date(date.today()), datetime)
        self.assertIsInstance(normalize_date(datetime.now()), datetime)
        self.assertEqual(normalize_date('123'), '123')
