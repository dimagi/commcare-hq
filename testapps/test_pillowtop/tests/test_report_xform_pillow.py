from django.test import TestCase, override_settings
from elasticsearch.exceptions import ConnectionError

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.change_feed.pillow import get_default_couch_db_change_feed_pillow
from corehq.apps.change_feed.tests.utils import get_test_kafka_consumer, get_current_multi_topic_seq
from corehq.apps.es import FormES
from corehq.elastic import get_es_new
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends
from corehq.form_processor.utils import TestFormMetadata
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.pillows.mappings.reportxform_mapping import REPORT_XFORM_INDEX_INFO
from corehq.pillows.reportxform import ReportXFormPillow, get_report_xform_to_elasticsearch_pillow
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup, get_form_ready_to_save
from couchforms.models import XFormInstance
from pillowtop.es_utils import initialize_index_and_mapping
from pillowtop.feed.couch import get_current_seq

DOMAIN = 'report-xform-pillowtest-domain'


@override_settings(ES_XFORM_FULL_INDEX_DOMAINS=[DOMAIN])
class ReportXformPillowTest(TestCase):

    def setUp(self):
        super(ReportXformPillowTest, self).setUp()
        FormProcessorTestUtils.delete_all_xforms()
        with trap_extra_setup(ConnectionError):
            self.elasticsearch = get_es_new()
            ensure_index_deleted(REPORT_XFORM_INDEX_INFO.index)
            initialize_index_and_mapping(self.elasticsearch, REPORT_XFORM_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(REPORT_XFORM_INDEX_INFO.index)
        super(ReportXformPillowTest, self).tearDown()

    def test_report_xform_pillow_couch(self):
        couch_seq = get_current_seq(XFormInstance.get_db())

        # make a form
        metadata = TestFormMetadata(domain=DOMAIN)
        form = get_form_ready_to_save(metadata)
        FormProcessorInterface(domain=DOMAIN).save_processed_models([form])
        self.addCleanup(form.delete)

        # send to elasticsearch
        self._sync_couch_xforms_to_es(since=couch_seq)

        # verify there
        results = FormES("report_xforms").run()
        self.assertEqual(1, results.total, results.hits)
        form_doc = results.hits[0]
        self.assertEqual(DOMAIN, form_doc['domain'])
        self.assertEqual(metadata.xmlns, form_doc['xmlns'])
        self.assertEqual('XFormInstance', form_doc['doc_type'])
        self.assertEqual(form.form_id, form_doc['_id'])

    def test_unsupported_domain(self):
        couch_seq = get_current_seq(XFormInstance.get_db())

        # make a form
        metadata = TestFormMetadata(domain='unsupported-domain')
        form = get_form_ready_to_save(metadata)
        FormProcessorInterface(domain='unsupported-domain').save_processed_models([form])
        self.addCleanup(form.delete)

        # send to elasticsearch
        self._sync_couch_xforms_to_es(since=couch_seq)

        # verify there
        results = FormES("report_xforms").run()
        self.assertEqual(0, results.total)

    @run_with_all_backends
    def test_report_xform_kafka_pillow(self):
        consumer = get_test_kafka_consumer(topics.FORM, topics.FORM_SQL)
        # have to get the seq id before the change is processed
        kafka_seq = get_current_multi_topic_seq([topics.FORM, topics.FORM_SQL])
        couch_seq = get_current_seq(XFormInstance.get_db())

        # make a form
        metadata = TestFormMetadata(domain=DOMAIN)
        form = get_form_ready_to_save(metadata)
        FormProcessorInterface(domain=DOMAIN).save_processed_models([form])

        if not should_use_sql_backend(DOMAIN):
            # publish couch changes to kafka
            couch_producer_pillow = get_default_couch_db_change_feed_pillow('test-report-xform-couch-pillow')
            couch_producer_pillow.process_changes(since=couch_seq, forever=False)

        # confirm change made it to kafka
        message = consumer.next()
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(form.form_id, change_meta.document_id)
        self.assertEqual(DOMAIN, change_meta.domain)

        # send to elasticsearch
        report_xform_kafka_pillow = get_report_xform_to_elasticsearch_pillow()
        report_xform_kafka_pillow.process_changes(since=kafka_seq, forever=False)
        self.elasticsearch.indices.refresh(REPORT_XFORM_INDEX_INFO.index)

        # confirm change made it to elasticserach
        results = FormES("report_xforms").remove_default_filters().run()
        self.assertEqual(1, results.total, results.hits)
        form_doc = results.hits[0]
        self.assertEqual(DOMAIN, form_doc['domain'])
        self.assertEqual(metadata.xmlns, form_doc['xmlns'])
        self.assertEqual('XFormInstance', form_doc['doc_type'])
        self.assertEqual(form.form_id, form_doc['_id'])

    def _sync_couch_xforms_to_es(self, since=0):
        ReportXFormPillow().process_changes(since=since, forever=False)
        self.elasticsearch.indices.refresh(REPORT_XFORM_INDEX_INFO.index)
