from django.test import SimpleTestCase
from corehq.apps.app_manager.xpath_validator import validate_xpath
from corehq.apps.app_manager.xpath_validator.wrapper import XpathValidationResponse


class XpathValidatorTest(SimpleTestCase):
    def test_simple_valid(self):
        self.assertEqual(
            validate_xpath('/data/node'),
            XpathValidationResponse(is_valid=True, message=None))

    def test_simple_invalid(self):
        self.assertEqual(
            validate_xpath('data node'),
            XpathValidationResponse(is_valid=False, message=
"""Lexical error on line 1. Unrecognized text.
data node
-----^
"""))

    def test_real_valid(self):
        self.assertEqual(
            validate_xpath(
                "if(count(instance('commcaresession')/session/user/data/commcare_location_id) > 0, instance('commcaresession')/session/user/data/commcare_location_id, /data/meta/userID)"),
            XpathValidationResponse(is_valid=True, message=None))

    def test_real_invalid(self):
        self.assertEqual(
            validate_xpath(
                "if(count(instance('commcaresession')/session/user/data/commcare_location_id) &gt; 0, instance('commcaresession')/session/user/data/commcare_location_id, /data/meta/userID)"),
            XpathValidationResponse(is_valid=False, message=
"""Lexical error on line 1. Unrecognized text.
...mmcare_location_id) &gt; 0, instance('co
-----------------------^
"""))
