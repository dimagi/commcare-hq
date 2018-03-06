from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

from django.test import TestCase
from elasticsearch.exceptions import ConnectionError

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.change_feed.pillow import get_application_db_kafka_pillow
from corehq.apps.change_feed.tests.utils import get_test_kafka_consumer
from corehq.apps.change_feed.topics import get_topic_offset
from corehq.apps.es import AppES
from corehq.elastic import get_es_new
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.application import get_app_to_elasticsearch_pillow
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
        ensure_index_deleted(APP_INDEX_INFO.index)
        super(AppPillowTest, self).tearDown()

    def test_app_pillow_kafka(self):
        consumer = get_test_kafka_consumer(topics.APP)
        # have to get the seq id before the change is processed
        kafka_seq = get_topic_offset(topics.APP)
        couch_seq = get_current_seq(Application.get_db())

        app_name = 'app-{}'.format(uuid.uuid4().hex)
        app = self._create_app(app_name)

        app_db_pillow = get_application_db_kafka_pillow('test_app_db_pillow')
        app_db_pillow.process_changes(couch_seq, forever=False)

        # confirm change made it to kafka
        message = next(consumer)
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(app._id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)

        # send to elasticsearch
        app_pillow = get_app_to_elasticsearch_pillow()
        app_pillow.process_changes(since=kafka_seq, forever=False)
        self.es.indices.refresh(APP_INDEX_INFO.index)

        # confirm change made it to elasticserach
        results = AppES().run()
        self.assertEqual(1, results.total)
        app_doc = results.hits[0]
        self.assertEqual(self.domain, app_doc['domain'])
        self.assertEqual(app['_id'], app_doc['_id'])
        self.assertEqual(app_name, app_doc['name'])

    def _create_app(self, name):
        factory = AppFactory(domain=self.domain, name=name, build_version='2.11')
        module1, form1 = factory.new_basic_module('open_case', 'house')
        factory.form_opens_case(form1)
        app = factory.app
        app.save()
        self.addCleanup(app.delete)
        return app
