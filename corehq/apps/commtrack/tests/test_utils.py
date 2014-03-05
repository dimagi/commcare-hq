#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from django.test import TestCase
from corehq.apps.commtrack.util import unicode_slug


class CommtrackUtilsTest(TestCase):

    def test_unicode_slug(self):
        test_cases = (
            ('normal', 'normal'),
            (u'unicode', 'unicode'),
            ('    with\n\t  whitespace   ', 'with-whitespace'),
            (u'speçial çháracters', 'special-characters'),
            (u'हिंदी', 'hindii'),
        )
        for input, output in test_cases:
            self.assertEqual(output, unicode_slug(input))