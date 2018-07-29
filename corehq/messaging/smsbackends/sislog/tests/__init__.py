from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.testcases import TestCase
from corehq.messaging.smsbackends.sislog.util import convert_raw_string


class GSM0338Portuguese(TestCase):

    def test_decode(self):
        raw_to_clean = {
            # basic character test
            "associa\x09\x7bo": "associa\u00e7\u00e3o",

            # extended character test
            "a\x09\x1b\x75car": "a\u00e7\u00facar",

            # no decode
            "no decode needed": "no decode needed",
        }
        for raw, expected in raw_to_clean.items():
            cleaned = convert_raw_string(raw)
            self.assertEqual(cleaned, expected)
            print("Cleaned text: %s" % cleaned)

