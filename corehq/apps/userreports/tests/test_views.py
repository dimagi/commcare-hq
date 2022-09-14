from django.test import SimpleTestCase
from django.utils.safestring import SafeString

from ..views import NamedExpressionHighlighter


class NamedExpressionHighlighterTests(SimpleTestCase):
    def test_normal_text_has_no_changes(self):
        self.assertEqual(NamedExpressionHighlighter.highlight_links('normalText'), 'normalText')

    def test_named_filter_is_highlighted(self):
        highlighted = NamedExpressionHighlighter.highlight_links('NamedFilter:abc')
        self.assertHTMLEqual(highlighted, '<a href="#NamedFilter:abc">NamedFilter:abc</a>')

    def test_result_is_html_safe(self):
        highlighted = NamedExpressionHighlighter.highlight_links('NamedFilter:abc')
        self.assertIsInstance(highlighted, SafeString)
