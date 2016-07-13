import uuid

from django.test import TestCase, override_settings
from elasticsearch.exceptions import ConnectionError

from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import change_meta_from_kafka_message
from corehq.apps.change_feed.pillow import get_default_couch_db_change_feed_pillow
from corehq.apps.change_feed.tests.utils import get_test_kafka_consumer
from corehq.apps.change_feed.topics import get_multi_topic_offset
from corehq.apps.es import CaseES
from corehq.elastic import get_es_new
from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX_INFO
from corehq.pillows.reportcase import ReportCasePillow, get_report_case_to_elasticsearch_pillow
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup, create_and_save_a_case
from pillowtop.es_utils import initialize_index_and_mapping
from pillowtop.feed.couch import get_current_seq

DOMAIN = 'report-case-pillowtest-domain'


@override_settings(ES_CASE_FULL_INDEX_DOMAINS=[DOMAIN])
class ReportCasePillowTest(TestCase):

    def setUp(self):
        super(ReportCasePillowTest, self).setUp()
        FormProcessorTestUtils.delete_all_cases()
        with trap_extra_setup(ConnectionError):
            self.elasticsearch = get_es_new()
            ensure_index_deleted(REPORT_CASE_INDEX_INFO.index)
            initialize_index_and_mapping(self.elasticsearch, REPORT_CASE_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(REPORT_CASE_INDEX_INFO.index)
        super(ReportCasePillowTest, self).tearDown()

    def test_report_case_pillow_couch(self):
        couch_seq = get_current_seq(CommCareCase.get_db())

        # make a case
        case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        case = create_and_save_a_case(DOMAIN, case_id, case_name)
        self.addCleanup(case.delete)

        # send to elasticsearch
        self._sync_couch_cases_to_es(since=couch_seq)

        # verify there
        results = CaseES('report_cases').run()
        self.assertEqual(1, results.total)
        case_doc = results.hits[0]
        self.assertEqual(DOMAIN, case_doc['domain'])
        self.assertEqual(case_id, case_doc['_id'])
        self.assertEqual(case_name, case_doc['name'])

    def test_case_unsupported_domain(self):
        couch_seq = get_current_seq(CommCareCase.get_db())

        # make a case
        case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        case = create_and_save_a_case('another-domain', case_id, case_name)
        self.addCleanup(case.delete)

        # send to elasticsearch
        self._sync_couch_cases_to_es(since=couch_seq)

        # verify there
        results = CaseES('report_cases').run()
        self.assertEqual(0, results.total)

    @run_with_all_backends
    def test_report_case_kafka_pillow(self):
        consumer = get_test_kafka_consumer(topics.CASE, topics.CASE_SQL)
        # have to get the seq id before the change is processed
        kafka_seq = get_multi_topic_offset([topics.CASE, topics.CASE_SQL])
        couch_seq = get_current_seq(CommCareCase.get_db())

        # make a case
        case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)
        case = create_and_save_a_case(DOMAIN, case_id, case_name)

        if not should_use_sql_backend(DOMAIN):
            # publish couch changes to kafka
            couch_producer_pillow = get_default_couch_db_change_feed_pillow('test-report-case-couch-pillow')
            couch_producer_pillow.process_changes(since=couch_seq, forever=False)

        # confirm change made it to kafka
        message = consumer.next()
        change_meta = change_meta_from_kafka_message(message.value)
        self.assertEqual(case.case_id, change_meta.document_id)
        self.assertEqual(DOMAIN, change_meta.domain)

        # send to elasticsearch
        report_case_kafka_pillow = get_report_case_to_elasticsearch_pillow()
        report_case_kafka_pillow.process_changes(since=kafka_seq, forever=False)
        self.elasticsearch.indices.refresh(REPORT_CASE_INDEX_INFO.index)

        # confirm change made it to elasticserach
        results = CaseES('report_cases').run()
        self.assertEqual(1, results.total)
        case_doc = results.hits[0]
        self.assertEqual(DOMAIN, case_doc['domain'])
        self.assertEqual(case_id, case_doc['_id'])
        self.assertEqual(case_name, case_doc['name'])

    def _sync_couch_cases_to_es(self, since=0):
        ReportCasePillow().process_changes(since=since, forever=False)
        self.elasticsearch.indices.refresh(REPORT_CASE_INDEX_INFO.index)
