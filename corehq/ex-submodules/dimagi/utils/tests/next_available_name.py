from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from dimagi.utils.next_available_name import next_available_name


class NextAvailableNameTest(SimpleTestCase):
    def test_next_available_name(self):
        self.assertEquals(next_available_name("abc", []), "abc-1")
        self.assertEquals(next_available_name("abc", ["abc-1", "abc-2"]), "abc-3")
        self.assertEquals(next_available_name("abc", ["abc-1", "abc-8"]), "abc-9")
