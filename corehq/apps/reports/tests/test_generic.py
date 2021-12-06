from unittest import expectedFailure

from django.utils.safestring import mark_safe
from django.test import SimpleTestCase

from corehq.apps.reports.generic import GenericTabularReport

from ..generic import _sanitize_rows


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
        value = '<blink>182</blink>'
        value = GenericTabularReport._strip_tags(value)
        self.assertEqual(value, '182')

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


class SanitizeRowTests(SimpleTestCase):
    def test_normal_output(self):
        rows = [['One']]

        result = _sanitize_rows(rows)
        self.assertEqual(result[0], ['One'])

    def test_escapes_rows(self):
        rows = [['<script>Hello</script>']]

        result = _sanitize_rows(rows)
        self.assertEqual(result[0], ['&lt;script&gt;Hello&lt;/script&gt;'])

    def test_does_not_escape_safe_text(self):
        rows = [[mark_safe('<div>Safe!</div>')]]  # nosec: test data

        result = _sanitize_rows(rows)
        self.assertEqual(result[0], ['<div>Safe!</div>'])

    def test_handles_rows(self):
        rows = [
            ['One', 'Two'],
            ['Three', 'Four'],
            ['Five', 'Six']
        ]

        result = _sanitize_rows(rows)
        self.assertEqual(result[0], ['One', 'Two'])
        self.assertEqual(result[1], ['Three', 'Four'])
        self.assertEqual(result[2], ['Five', 'Six'])
