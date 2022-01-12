from django.test import SimpleTestCase
from ..html_utils import strip_tags


class StripTagsTests(SimpleTestCase):
    def test_leaves_plain_text_alone(self):
        self.assertEqual(strip_tags('plain text'), 'plain text')

    def test_strips_embedded_tag(self):
        self.assertEqual(strip_tags('This is <b>important</b>!'), 'This is important!')

    def test_removes_tags_with_attributes(self):
        self.assertEqual(strip_tags('<span style="color:#ffffff">Colored Text</span>'), 'Colored Text')
