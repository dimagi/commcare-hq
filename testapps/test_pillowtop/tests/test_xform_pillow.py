from django.test import TestCase, override_settings
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.es import FormES
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.utils import TestFormMetadata
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.xform import XFormPillow, get_sql_xform_to_elasticsearch_pillow
from corehq.util.elastic import delete_es_index, ensure_index_deleted
from corehq.util.test_utils import get_form_ready_to_save
from testapps.test_pillowtop.utils import get_test_kafka_consumer


class XFormPillowTest(TestCase):

    domain = 'xform-pillowtest-domain'

    def setUp(self):
        FormProcessorTestUtils.delete_all_xforms()
        self.pillow = XFormPillow()
        self.elasticsearch = self.pillow.get_es_new()
        delete_es_index(self.pillow.es_index)

    def tearDown(self):
        ensure_index_deleted(self.pillow.es_index)

    def test_xform_pillow_couch(self):
        metadata = TestFormMetadata(domain=self.domain)
        form = get_form_ready_to_save(metadata)
        FormProcessorInterface(domain=self.domain).save_processed_models([form])
        self.pillow.process_changes(since=0, forever=False)
        self.elasticsearch.indices.refresh(self.pillow.es_index)
        results = FormES().run()
        self.assertEqual(1, results.total)
        form_doc = results.hits[0]
        self.assertEqual(self.domain, form_doc['domain'])
        self.assertEqual(metadata.xmlns, form_doc['xmlns'])
        self.assertEqual('XFormInstance', form_doc['doc_type'])
        form.delete()

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_xform_pillow_sql(self):
        consumer = get_test_kafka_consumer(topics.FORM_SQL)

        # have to get the seq id before the change is processed
        kafka_seq = consumer.offsets()['fetch'][(topics.FORM_SQL, 0)]

        metadata = TestFormMetadata(domain=self.domain)
        form = get_form_ready_to_save(metadata, is_db_test=True)
        form_processor = FormProcessorInterface(domain=self.domain)
        form_processor.save_processed_models([form])

        # confirm change made it to kafka
        message = consumer.next()
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(form.form_id, change_meta.document_id)
        self.assertEqual(self.domain, change_meta.domain)

        # send to elasticsearch
        sql_pillow = get_sql_xform_to_elasticsearch_pillow()
        sql_pillow.process_changes(since=kafka_seq, forever=False)
        self.elasticsearch.indices.refresh(self.pillow.es_index)

        # confirm change made it to elasticserach
        results = FormES().run()
        self.assertEqual(1, results.total)
        form_doc = results.hits[0]
        self.assertEqual(self.domain, form_doc['domain'])
        self.assertEqual(metadata.xmlns, form_doc['xmlns'])
        self.assertEqual('XFormInstance', form_doc['doc_type'])
