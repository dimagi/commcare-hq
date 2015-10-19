#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from corehq.apps.sms.util import clean_phone_number, clean_outgoing_sms_text
from django.test import SimpleTestCase


class UtilTestCase(SimpleTestCase):
    
    def setUp(self):
        pass

    def testCleanPhoneNumber(self):
        phone_number = "  324 23-23421241"
        cleaned = clean_phone_number(phone_number)
        self.assertEquals(cleaned, "+3242323421241")

    def testCleanOutgoingSMSText(self):
        text = u"+this is a test شسیبشسی"
        cleaned = clean_outgoing_sms_text(text)
        # make sure '+' and unicode get encoded for GET properly
        self.assertEquals(cleaned, "%2Bthis%20is%20a%20test%20%D8%B4%D8%B3%DB%8C%D8%A8%D8%B4%D8%B3%DB%8C")
