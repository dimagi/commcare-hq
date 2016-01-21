from django.test import TestCase
from pillowtop.es_utils import completely_initialize_pillow_index
from pillowtop.tests import require_explicit_elasticsearch_testing

from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application
from corehq.pillows.application import AppPillow
from corehq.util.elastic import delete_es_index

from corehq.apps.users.views import get_domain_languages


class TestDomainLanguages(TestCase):
    @classmethod
    @require_explicit_elasticsearch_testing
    def setUpClass(cls):
        cls.domain = 'test-languages'

        cls.pillow = AppPillow(online=False)
        completely_initialize_pillow_index(cls.pillow)

        cls.app1 = Application.new_app(cls.domain, 'My Application 1', APP_V2)
        cls.app1.langs = ['en', 'es']
        cls.app1.save()
        cls.pillow.send_robust(cls.app1.to_json())
        cls.app2 = Application.new_app(cls.domain, 'My Application 2', APP_V2)
        cls.app2.langs = ['fr']
        cls.app2.save()
        cls.pillow.send_robust(cls.app2.to_json())

        cls.pillow.get_es_new().indices.refresh(cls.pillow.es_index)

    @classmethod
    def tearDownClass(cls):
        cls.app1.delete()
        cls.app2.delete()
        delete_es_index(cls.pillow.es_index)

    def test_get_domain_languages(self):
        self.assertEqual(
            [('en', 'en (English)'), ('es', 'es (Spanish)'), ('fr', 'fr')],
            get_domain_languages(self.domain)
        )
