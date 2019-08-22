from __future__ import absolute_import
from __future__ import unicode_literals
import copy
import re
import textwrap
from django.conf import settings
from django.template import Template, Context, TemplateSyntaxError
from django.test import SimpleTestCase, override_settings
from corehq.util.test_utils import make_make_path
from io import open

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
@override_settings(COMPRESS_ENABLED=False)
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

    def _test(self, filename, context):
        template = self._get_file('templates', '{}.html'.format(filename))
        actual = self._render_template(template, context)

        # Expected template shouldn't include the tag being rendered but may require other template tags
        expected_template = self._get_file('rendered', '{}.html'.format(filename))
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

    def test_javascript_libraries_jquery_only(self):
        self._test('javascript_libraries_jquery_only', {})

    def test_javascript_libraries_hq(self):
        self._test('javascript_libraries_hq', {
            'hq': True,
        })

    def test_requirejs_main(self):
        self.assertEqual(
            self.render("""
                {% extends "requirejs_base.html" %}
                {% load hq_shared_tags %}
                {% requirejs_main "requirejs/main" %}
                {% block content %}{{requirejs_main}}{% endblock %}
            """).strip(),
            "requirejs/main after tag\nrequirejs/main",
        )

    def test_requirejs_main_no_arg(self):
        # this version can be used in a base template that may or may not use requirejs
        self.assertEqual(
            self.render("""
                {% load hq_shared_tags %}
                {% requirejs_main %}
                {% if requirejs_main %}unexpected truth{% endif %}
                {{requirejs_main}}
            """).strip(),
            "None",
        )

    def test_requirejs_main_in_context(self):
        self.assertEqual(
            self.render(
                """
                {% extends "requirejs_base.html" %}
                {% load hq_shared_tags %}
                {% requirejs_main "requirejs/main" %}
                {% block content %}{{requirejs_main}}{% endblock %}
                """,
                {"requirejs_main": "rjs/context"}
            ).strip(),
            "rjs/context before tag\n\n"
            "rjs/context after tag\n"
            "rjs/context",
        )

    def test_requirejs_main_multiple_tags(self):
        msg = r"multiple 'requirejs_main' tags not allowed \(\"requirejs/two\"\)"
        with self.assertRaisesRegex(TemplateSyntaxError, msg):
            self.render("""
                {% load hq_shared_tags %}
                {% requirejs_main "requirejs/one" %}
                {% requirejs_main "requirejs/two" %}
            """)

    def test_requirejs_main_too_short(self):
        msg = r"bad 'requirejs_main' argument: '"
        with self.assertRaisesRegex(TemplateSyntaxError, msg):
            self.render("""
                {% load hq_shared_tags %}
                {% requirejs_main ' %}
            """)

    def test_requirejs_main_bad_string(self):
        msg = r"bad 'requirejs_main' argument: \.'"
        with self.assertRaisesRegex(TemplateSyntaxError, msg):
            self.render("""
                {% load hq_shared_tags %}
                {% requirejs_main .' %}
            """)

    def test_requirejs_main_mismatched_delimiter(self):
        msg = r"bad 'requirejs_main' argument: 'x\""
        with self.assertRaisesRegex(TemplateSyntaxError, msg):
            self.render("""
                {% load hq_shared_tags %}
                {% requirejs_main 'x" %}
            """)
