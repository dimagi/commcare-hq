from unittest import expectedFailure

from django.utils.safestring import mark_safe
from django.test import RequestFactory, SimpleTestCase

from corehq.apps.reports.exceptions import BadRequestError
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

    def test_pagination_exceeds_max_rows(self):
        class Report(GenericTabularReport):
            name = slug = "report"
            section_name = "reports"
            dispatcher = "fake"

            def _update_initial_context(self):
                """override to avoid database hit in test"""

        request = RequestFactory().get("/report", {"iDisplayLength": 1001})
        report = Report(request)
        with self.assertRaises(BadRequestError) as res:
            report.pagination
        self.assertEqual(str(res.exception), "Row count is too large")


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
