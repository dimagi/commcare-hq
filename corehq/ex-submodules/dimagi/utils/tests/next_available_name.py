from django.test import SimpleTestCase
from dimagi.utils.next_available_name import next_available_name


class NextAvailableNameTest(SimpleTestCase):
    def test_next_available_name(self):
        self.assertEqual(next_available_name("abc", []), "abc-1")
        self.assertEqual(next_available_name("abc", ["abc-1", "abc-2"]), "abc-3")
        self.assertEqual(next_available_name("abc", ["abc-1", "abc-8"]), "abc-9")
