from django.test import SimpleTestCase
from dimagi.utils.name_to_url import name_to_url

class NameToURLTest(SimpleTestCase):
    def test_name_to_url(self):
        self.assertEquals(name_to_url("I have  spaces"), "i-have-spaces")
