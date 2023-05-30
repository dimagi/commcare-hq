from django.test import TestCase

from corehq.apps.app_manager.models import Application
from corehq.apps.es.apps import app_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.views import get_domain_languages


@es_test(requires=[app_adapter], setup_class=True)
class TestDomainLanguages(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestDomainLanguages, cls).setUpClass()
        cls.domain = 'test-languages'

        cls.app1 = Application.new_app(cls.domain, 'My Application 1')
        cls.app1.langs = ['en', 'es']
        cls.app1.save()

        cls.app2 = Application.new_app(cls.domain, 'My Application 2')
        cls.app2.langs = ['fr']
        cls.app2.save()
        app_adapter.bulk_index([cls.app2, cls.app1], refresh=True)

    @classmethod
    def tearDownClass(cls):
        cls.app1.delete()
        cls.app2.delete()
        super(TestDomainLanguages, cls).tearDownClass()

    def test_get_domain_languages(self):
        self.assertEqual(
            [('en', 'en (English)'), ('es', 'es (Spanish)'), ('fr', 'fr')],
            get_domain_languages(self.domain)
        )
