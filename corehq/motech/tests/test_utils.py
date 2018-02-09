from __future__ import absolute_import
import doctest
from django.test import SimpleTestCase
import corehq.motech.utils


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.utils)
        self.assertEqual(results.failed, 0)
