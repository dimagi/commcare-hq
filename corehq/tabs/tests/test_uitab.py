from django.test import SimpleTestCase
from django.template import Context, Template
from django.core.cache.utils import make_template_fragment_key
from django.core.cache import cache

from corehq.tabs.uitab import UITab


class TestUITab(SimpleTestCase):
    def test_header_is_cached_correctly(self):
        context = self._generate_context()

        self._populate_cache(context)

        cache_key = make_template_fragment_key(UITab.fragment_prefix_name, context.values())
        self.assertIsNotNone(cache.get(cache_key))

    def test_header_cache_is_successfully_cleared(self):
        context = self._generate_context()
        self._populate_cache(context)

        self._clear_dropdown_cache()

        cache_key = make_template_fragment_key(UITab.fragment_prefix_name, context.values())
        self.assertIsNone(cache.get(cache_key))

    def test_cache_accounts_for_bootstrap_5(self):
        bootstrap5_context = self._generate_context(use_bootstrap5=True)
        self._populate_cache(bootstrap5_context)

        self._clear_dropdown_cache()

        cache_key = make_template_fragment_key(UITab.fragment_prefix_name, bootstrap5_context.values())
        self.assertIsNone(cache.get(cache_key))

    def setUp(self):
        # this template is intended to mimic the cache lines that can be found in the menu_main.html templates
        # fully rendering those templates felt too heavvy, as it would mean creating domain, user, etc.
        self.template = Template('''
        {% load cache %}

        {% cache 500 header_tab tab_name domain tab_is_active user_id role_version lang use_bootstrap5 %}
        <h1>Test</h1>
        {% endcache %}
        ''')

        self.domain = 'test-domain'
        self.user_id = '12345'
        self.role_version = 'Admin'
        self.lang = 'en'

        cache.clear()

    def _generate_context(self,
                          domain=None,
                          tab_is_active=True,
                          user_id=None,
                          role_version=None,
                          lang=None,
                          use_bootstrap5=False):
        return {
            'tab_name': UITab.class_name(),
            'domain': domain or self.domain,
            'tab_is_active': tab_is_active,
            'user_id': user_id or self.user_id,
            'role_version': role_version or self.role_version,
            'lang': lang or self.lang,
            'use_bootstrap5': use_bootstrap5
        }

    def _populate_cache(self, context):
        self.template.render(Context(context))

    def _clear_dropdown_cache(self, domain=None, user_id=None, role_version=None, lang=None):
        UITab.clear_dropdown_cache_impl(
            domain or self.domain,
            user_id or self.user_id,
            role_version or self.role_version,
            lang or self.lang
        )
