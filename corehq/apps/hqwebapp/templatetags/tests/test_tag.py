import copy
import re
import textwrap

from django.conf import settings
from django.template import Context, Template, TemplateSyntaxError
from django.test import SimpleTestCase, override_settings

from corehq.util.test_utils import make_make_path

_make_path = make_make_path(__file__)


def template_dirs(*relative_dirs):
    """Convenient decorator to specify the template path.

    Inspired by https://github.com/funkybob/django-sniplates/pull/47/files
    """
    # copy the original setting
    TEMPLATES = copy.deepcopy(settings.TEMPLATES)
    for tpl_cfg in TEMPLATES:
        tpl_cfg['DIRS'] = [_make_path(rel) for rel in relative_dirs]
    return override_settings(TEMPLATES=TEMPLATES)


@template_dirs("templates")
class TagTest(SimpleTestCase):

    @staticmethod
    def _normalize_whitespace(string):
        return re.sub(r'\s*\n+\s*', '\n', string).strip()

    @staticmethod
    def _render_template(template_string, context=None):
        return Template(template_string).render(Context(context or {}))

    @classmethod
    def render(cls, template_string, context=None):
        temp = textwrap.dedent(template_string).lstrip()
        return cls._render_template(temp, context)

    @staticmethod
    def _get_file(*args):
        with open(_make_path(*args)) as f:
            return f.read()

    def _test(self, filename, context, rendered_filename=None):
        template = self._get_file('templates', '{}.html'.format(filename))
        actual = self._render_template(template, context)

        # Expected template shouldn't include the tag being rendered but may require other template tags
        rendered_filename = rendered_filename or filename
        expected_template = self._get_file('rendered', '{}.html'.format(rendered_filename))
        expected = self._render_template(expected_template)

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
        # why does this test take 8s?
        self._test('registerurl', {
            'domain': 'hqsharedtags'
        })

    def test_js_entry(self):
        self.assertEqual(
            self.render("""
                {% extends "webpack_base.html" %}
                {% load hq_shared_tags %}
                {% js_entry "webpack/main" %}
                {% block content %}{{js_entry}}{% endblock %}
            """).strip(),
            "webpack/main after tag\nwebpack/main",
        )

    def test_js_entry_no_arg(self):
        # this version can be used in a base template that may or may not use webpack
        self.assertEqual(
            self.render("""
                {% load hq_shared_tags %}
                {% js_entry %}
                {% if js_entry %}unexpected truth 2{% endif %}
                {{js_entry}}
            """).strip(),
            "",
        )

    def test_js_entry_in_context(self):
        self.assertEqual(
            self.render(
                """
                {% extends "webpack_base.html" %}
                {% load hq_shared_tags %}
                {% js_entry "webpack/main" %}
                {% block content %}{{js_entry}}{% endblock %}
                """,
                {"js_entry": "webpack/context"}
            ).strip(),
            "webpack/context before tag\n\n"
            "webpack/context after tag\n"
            "webpack/context",
        )

    def test_js_entry_multiple_tags(self):
        msg = r"multiple 'js_entry' tags not allowed \(\"webpack/two\"\)"
        with self.assertRaisesRegex(TemplateSyntaxError, msg):
            self.render("""
                {% load hq_shared_tags %}
                {% js_entry "webpack/one" %}
                {% js_entry "webpack/two" %}
            """)

    def test_js_entry_too_short(self):
        msg = r"bad 'js_entry' argument: '"
        with self.assertRaisesRegex(TemplateSyntaxError, msg):
            self.render("""
                {% load hq_shared_tags %}
                {% js_entry ' %}
            """)

    def test_js_entry_bad_string(self):
        msg = r"bad 'js_entry' argument: \.'"
        with self.assertRaisesRegex(TemplateSyntaxError, msg):
            self.render("""
                {% load hq_shared_tags %}
                {% js_entry .' %}
            """)

    def test_js_entry_mismatched_delimiter(self):
        msg = r"bad 'js_entry' argument: 'x\""
        with self.assertRaisesRegex(TemplateSyntaxError, msg):
            self.render("""
                {% load hq_shared_tags %}
                {% js_entry 'x" %}
            """)
