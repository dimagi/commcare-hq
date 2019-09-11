from django.test import TestCase

from elasticsearch.exceptions import ConnectionError

from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.app_manager.models import Application
from corehq.apps.users.views import get_domain_languages
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.pillows.mappings.app_mapping import APP_INDEX_INFO
from corehq.util.elastic import delete_es_index
from corehq.util.test_utils import trap_extra_setup


class TestDomainLanguages(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestDomainLanguages, cls).setUpClass()
        cls.domain = 'test-languages'

        with trap_extra_setup(ConnectionError):
            cls.es = get_es_new()
            initialize_index_and_mapping(cls.es, APP_INDEX_INFO)

        cls.app1 = Application.new_app(cls.domain, 'My Application 1')
        cls.app1.langs = ['en', 'es']
        cls.app1.save()
        send_to_elasticsearch('apps', cls.app1.to_json())
        cls.app2 = Application.new_app(cls.domain, 'My Application 2')
        cls.app2.langs = ['fr']
        cls.app2.save()
        send_to_elasticsearch('apps', cls.app2.to_json())

        cls.es.indices.refresh(APP_INDEX_INFO.index)

    @classmethod
    def tearDownClass(cls):
        cls.app1.delete()
        cls.app2.delete()
        delete_es_index(APP_INDEX_INFO.index)
        super(TestDomainLanguages, cls).tearDownClass()

    def test_get_domain_languages(self):
        self.assertEqual(
            [('en', 'en (English)'), ('es', 'es (Spanish)'), ('fr', 'fr')],
            get_domain_languages(self.domain)
        )
