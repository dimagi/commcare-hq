import langcodes
from django.test import TestCase

from corehq.apps.app_manager.models import Application
from corehq.apps.es.apps import app_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.views import get_domain_languages


@es_test(requires=[app_adapter], setup_class=True)
class TestDomainLanguages(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-languages'

        cls.app1 = Application.new_app(cls.domain, 'My Application 1')
        cls.app1.langs = ['en', 'es']
        cls.app1.save()
        cls.addClassCleanup(cls.app1.delete)

        cls.app2 = Application.new_app(cls.domain, 'My Application 2')
        cls.app2.langs = ['fr']
        cls.app2.save()
        cls.addClassCleanup(cls.app2.delete)
        app_adapter.bulk_index([cls.app2, cls.app1], refresh=True)

    def test_returns_translated_languages_for_domain(self):
        langs = get_domain_languages(self.domain)
        assert langs == [('en', 'en (English)'), ('es', 'es (Spanish)'), ('fr', 'fr')]

    def test_default_to_all_langs(self):
        assert get_domain_languages('random-domain') == []

        langs = get_domain_languages('random-domain', default_to_all_langs=True)
        assert langs == langcodes.get_all_langs_for_select()

        langs = get_domain_languages(self.domain, default_to_all_langs=True)
        assert langs == [('en', 'en (English)'), ('es', 'es (Spanish)'), ('fr', 'fr')]
