from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from casexml.apps.case.templatetags.case_tags import normalize_date
from datetime import date, datetime


class TestCaseTags(SimpleTestCase):

    def test_normalize_date(self):
        self.assertIsInstance(normalize_date(date.today()), datetime)
        self.assertIsInstance(normalize_date(datetime.utcnow()), datetime)
        self.assertEqual(normalize_date('123'), '123')
