from __future__ import absolute_import
from __future__ import unicode_literals
import doctest
from django.test import SimpleTestCase
import corehq.motech.value_source


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.value_source)
        self.assertEqual(results.failed, 0)
