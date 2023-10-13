from django.test import SimpleTestCase

from django.utils.safestring import SafeString
from django.utils.html import format_html

from ...utils.html import safe_replace


class SafeReplaceTests(SimpleTestCase):
    def test_replacement_is_html_safe(self):
        def replace_fun(token):
            return 'replaced'

        result = safe_replace(r'Hello', replace_fun, 'Hello World')
        self.assertIsInstance(result, SafeString)

    def test_no_matches_returns_full_string(self):
        def noop(match):
            return match.group()

        result = safe_replace(r'gibberishPattern', noop, 'Hello World')
        self.assertEqual(result, 'Hello World')

    def test_replacement_is_escaped(self):
        def replace_fun(match):
            return f'<{match.group()}>'

        result = safe_replace(r'Hello', replace_fun, 'Hello World')
        self.assertEqual(result, '&lt;Hello&gt; World')

    def test_sanitized_replacement_is_left_alone(self):
        def replace_fun(match):
            return format_html('<{}>', match.group())

        result = safe_replace(r'Hello', replace_fun, 'Hello World')
        self.assertEqual(result, '<Hello> World')

    def test_replacement_is_applied_globally(self):
        def replace_fun(match):
            return 'replaced'

        result = safe_replace(r'Hello', replace_fun, 'Hello 1 Hello 2 Hello 3 Hello')
        self.assertEqual(result, 'replaced 1 replaced 2 replaced 3 replaced')
