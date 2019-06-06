from __future__ import absolute_import
from __future__ import unicode_literals
import doctest
import six
from django.test import SimpleTestCase
import corehq.motech.utils
from corehq.motech.utils import pad, pformat_json


class PadTests(SimpleTestCase):

    def test_assertion(self):
        with self.assertRaises(AssertionError):
            pad('xyzzy', 8, b'*')

    def test_ascii_bytestring_default_char(self):
        padded = pad(b'xyzzy', 8)
        self.assertEqual(padded, b'xyzzy   ')

    def test_nonascii(self):
        """
        pad should pad a string according to its size in bytes, not its length in letters.
        """
        padded = pad(b'xy\xc5\xba\xc5\xbay', 8, b'*')
        self.assertEqual(padded, b'xy\xc5\xba\xc5\xbay*')


class PFormatJSONTests(SimpleTestCase):

    def test_valid_json(self):
        self.assertEqual(
            pformat_json('{"ham": "spam", "eggs": "spam"}'),
            '{\n  "eggs": "spam",\n  "ham": "spam"\n}' if six.PY3 else '{\n  "eggs": "spam", \n  "ham": "spam"\n}'
        )
        self.assertEqual(
            pformat_json({'ham': 'spam', 'eggs': 'spam'}),
            '{\n  "eggs": "spam",\n  "ham": "spam"\n}' if six.PY3 else '{\n  "eggs": "spam", \n  "ham": "spam"\n}'
        )

    def test_invalid_json(self):
        self.assertEqual(
            pformat_json('ham spam eggs spam'),
            'ham spam eggs spam'
        )

    def test_empty_string(self):
        self.assertEqual(
            pformat_json(''),
            ''
        )

    def test_none(self):
        self.assertEqual(
            pformat_json(None),
            ''
        )

class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.utils)
        self.assertEqual(results.failed, 0)
