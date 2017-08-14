import re
from django.template import Template, Context
from django.test import SimpleTestCase
from corehq.util.test_utils import make_make_path

_make_path = make_make_path(__file__)


class TagTest(SimpleTestCase):
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

    def _test(self, filename, context):
        actual = self._render_template(self._get_file('templates', '{}.html'.format(filename)), context)
        expected = self._get_file('rendered', '{}.html'.format(filename))

        self.assertEqual(
            self._normalize_whitespace(actual),
            self._normalize_whitespace(expected),
        )

    def test_initial_page_data(self):
        self._test('initial_page_data', {
            'scalar': "estrella",
            'special_chars': "here's \"something\" irritating to parse & deal with",
            'list': [1, 2, 3],
            'maps': [
                {'hen': 'brood'},
                {'nightingale': 'watch'},
                {'quail': 'bevy'},
                {'starling': 'murmuration'},
            ],
        })

    def test_registerurl(self):
        self._test('registerurl', {
            'domain': 'hqsharedtags'
        })
