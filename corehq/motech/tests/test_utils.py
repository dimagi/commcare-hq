from __future__ import absolute_import
from __future__ import unicode_literals
import doctest
from django.test import SimpleTestCase
import corehq.motech.utils
from corehq.motech.utils import pad


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


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.utils)
        self.assertEqual(results.failed, 0)
