from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from dimagi.utils.name_to_url import name_to_url


class NameToURLTest(SimpleTestCase):
    def test_name_to_url(self):
        self.assertEquals(name_to_url("I have  spaces"), "i-have-spaces")
        self.assertEquals(name_to_url("\u00f5", "project"), "project")
        self.assertEquals(name_to_url("thing \u00f5", "project"), "thing")
        self.assertEquals(name_to_url("abc \u00f5 def"), "abc-def")
