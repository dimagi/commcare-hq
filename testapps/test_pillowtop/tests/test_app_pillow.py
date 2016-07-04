from django.test import TestCase
from elasticsearch.exceptions import ConnectionError

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests import AppFactory
from corehq.apps.es import AppES
from corehq.elastic import get_es_new
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.application import AppPillow
from corehq.pillows.mappings.app_mapping import APP_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from pillowtop.es_utils import initialize_index_and_mapping
from pillowtop.feed.couch import get_current_seq


class AppPillowTest(TestCase):

    domain = 'app-pillowtest-domain'

    def setUp(self):
        super(AppPillowTest, self).setUp()
        FormProcessorTestUtils.delete_all_cases()
        with trap_extra_setup(ConnectionError):
            self.es = get_es_new()

        ensure_index_deleted(APP_INDEX_INFO.index)
        initialize_index_and_mapping(self.es, APP_INDEX_INFO)

    def tearDown(self):
        # ensure_index_deleted(APP_INDEX_INFO.index)
        super(AppPillowTest, self).tearDown()

    def test_app_pillow_couch(self):
        since = get_current_seq(Application.get_db())

        name = 'test app 1'
        app = self._create_app(name)
        pillow = AppPillow()
        pillow.process_changes(since, forever=False)
        self.es.indices.refresh(APP_INDEX_INFO.index)

        # verify there
        results = AppES().run()
        self.assertEqual(1, results.total)
        app_doc = results.hits[0]
        self.assertEqual(self.domain, app_doc['domain'])
        self.assertEqual(app['_id'], app_doc['_id'])
        self.assertEqual(name, app_doc['name'])

    def _create_app(self, name):
        factory = AppFactory(domain=self.domain, name=name, build_version='2.11')
        module1, form1 = factory.new_basic_module('open_case', 'house')
        factory.form_opens_case(form1)
        app = factory.app
        app.save()
        self.addCleanup(app.delete)
        return app
