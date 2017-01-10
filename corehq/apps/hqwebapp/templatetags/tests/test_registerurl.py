import re
from django.template import Template, Context
from django.test import SimpleTestCase
from corehq.util.test_utils import make_make_path

_make_path = make_make_path(__file__)


class RegisterurlTest(SimpleTestCase):
    @staticmethod
    def _normalize_whitespace(string):
        return re.sub(r'\s*\n+\s*', '\n', string).strip()

    @staticmethod
    def _render_template(template_string, context):
        return Template(template_string).render(Context(context))

    @staticmethod
    def _get_file(*args):
        with open(_make_path(*args)) as f:
            return f.read()

    def test(self):
        actual = self._render_template(self._get_file('templates', 'registerurl.html'), {
            'domain': 'hqsharedtags'
        })
        expected = self._get_file('rendered', 'registerurl.html')

        self.assertEqual(
            self._normalize_whitespace(actual),
            self._normalize_whitespace(expected),
        )
