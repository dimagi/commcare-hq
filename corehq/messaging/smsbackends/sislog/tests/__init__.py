from django.test.testcases import TestCase
from corehq.messaging.smsbackends.sislog.util import convert_raw_string

class GSM0338Portuguese(TestCase):
    def test_decode(self):
        raw_to_clean = {
            # basic character test
            u"associa\x09\x7bo": u"associa\u00e7\u00e3o",

            # extended character test
            u"a\x09\x1b\x75car": u"a\u00e7\u00facar",

            # no decode
            u"no decode needed": u"no decode needed",
        }
        for raw, expected in raw_to_clean.items():
            cleaned = convert_raw_string(raw)
            self.assertEqual(cleaned, expected)
            print "Cleaned text: %s" % cleaned

