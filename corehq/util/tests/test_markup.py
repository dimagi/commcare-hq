from django.test import SimpleTestCase
from django.utils.safestring import SafeString
from corehq.util.markup import mark_up_urls

__test__ = {
    'mark_up_urls': mark_up_urls
}


class TestMarkUpURLs(SimpleTestCase):
    def test_handles_empty_string(self):
        result = mark_up_urls('')
        self.assertEqual(result, '')

    def test_string_without_urls_returns_string(self):
        result = mark_up_urls('This has no urls')
        self.assertEqual(result, 'This has no urls')

    def test_creates_markup(self):
        result = mark_up_urls('Please see http://google.com for more info.')
        self.assertEqual(result, 'Please see <a href="http://google.com">http://google.com</a> for more info.')

    def test_marksup_multiple_urls(self):
        result = mark_up_urls("http://commcarehq.org redirects to https://commcarehq.org.")
        self.assertEqual(result,
            '<a href="http://commcarehq.org">http://commcarehq.org</a>'
            ' redirects to <a href="https://commcarehq.org">https://commcarehq.org</a>.')

    def test_output_with_urls_is_safe(self):
        result = mark_up_urls('this points to http://google.com')
        self.assertIsInstance(result, SafeString)
