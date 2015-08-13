from unittest import expectedFailure
from corehq.apps.reports.generic import GenericTabularReport
from django.test import SimpleTestCase


class GenericTabularReportTests(SimpleTestCase):

    def test_strip_tags_html_bytestring(self):
        """
        _strip_tags should strip HTML tags
        """
        value = '<blink>182</blink>'
        value = GenericTabularReport._strip_tags(value)
        self.assertEqual(value, '182')

    def test_strip_tags_html_unicode(self):
        """
        _strip_tags should strip HTML tags from Unicode
        """
        value = u'<blink>182</blink>'
        value = GenericTabularReport._strip_tags(value)
        self.assertEqual(value, u'182')

    def test_strip_tags_passthru(self):
        """
        _strip_tags should allow non-basestring values to pass through
        """
        value = {'blink': 182}
        value = GenericTabularReport._strip_tags(value)
        self.assertEqual(value, {'blink': 182})

    @expectedFailure
    def test_strip_tags_expected_fail(self):
        """
        _strip_tags should not strip strings inside angle brackets, but does
        """
        value = '1 < 8 > 2'
        value = GenericTabularReport._strip_tags(value)
        self.assertEqual(value, '1 < 8 > 2')
