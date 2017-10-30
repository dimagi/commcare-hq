from django.test import SimpleTestCase

import casexml.apps.phone.utils as mod


class TestUtils(SimpleTestCase):

    def test_get_cached_items_with_count_no_count(self):
        XML = b'<fixture />'
        xml, num = mod.get_cached_items_with_count(XML)
        self.assertEqual(xml, XML)
        self.assertEqual(num, 1)

    def test_get_cached_items_with_count(self):
        XML = b'<!--items=42--><fixture>...</fixture>'
        xml, num = mod.get_cached_items_with_count(XML)
        self.assertEqual(xml, b'<fixture>...</fixture>')
        self.assertEqual(num, 42)

    def test_get_cached_items_with_count_bad_format(self):
        XML = b'<!--items=2JUNK--><fixture>...</fixture>'
        xml, num = mod.get_cached_items_with_count(XML)
        self.assertEqual(xml, XML)
        self.assertEqual(num, 1)
