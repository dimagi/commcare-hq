# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
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

    def test_whitespace(self):
        self.assertEqual(
            validate_xpath('\n1 =\t2\r + 3'),
            XpathValidationResponse(is_valid=True, message=None))

    def test_unicode(self):
        self.assertEqual(
            validate_xpath('"Serviços e Supervisão"'),
            XpathValidationResponse(is_valid=True, message=None))

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

    def test_good_hashtag(self):
        self.assertEqual(
            validate_xpath('#session'),
            XpathValidationResponse(is_valid=True, message=None))

    def test_bad_hashtag(self):
        self.assertEqual(
            validate_xpath('#hashtag'),
            XpathValidationResponse(is_valid=False,
                                    message="hashtag is not a valid # expression\n"))

    def test_case_hashtag(self):
        self.assertEqual(
            validate_xpath('#case', allow_case_hashtags=True),
            XpathValidationResponse(is_valid=True, message=None))

    def test_disallowed_case_hashtag(self):
        self.assertEqual(
            validate_xpath('#case', allow_case_hashtags=False),
            XpathValidationResponse(is_valid=False,
                                    message="case is not a valid # expression\n"))
