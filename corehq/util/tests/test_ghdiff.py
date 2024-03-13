from django.test import SimpleTestCase

from corehq.util import ghdiff


class GhDiffTest(SimpleTestCase):

    def test_diff(self):
        text_1 = "foobar"
        text_2 = "foobarbaz"
        output = ghdiff.diff(text_1, text_2)
        self.assertTrue("-foobar" in output)
        self.assertTrue('+foobar<span class="highlight">baz</span>' in output)

    def test_no_css_option(self):
        text_1 = "foobar"
        text_2 = "foobarbaz"
        output = ghdiff.diff(text_1, text_2, css=False)
        self.assertFalse("<style" in output)
